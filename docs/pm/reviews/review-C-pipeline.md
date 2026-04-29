---
review_id: review-C-pipeline
review_group: C
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---

# review-C-pipeline — orchestrator / pipeline / 调度

## 1. 范围确认

审阅文件清单（C 组白名单内）：

- `sources/base.py`（fetcher Protocol + Item / SourceQuery / REGISTRY）
- `sources/__init__.py`（空文件）
- `sources/fetchers/__init__.py`（注册触发）
- `sources/fetchers/arxiv.py`
- `sources/fetchers/hf_papers.py`
- `sources/pdf_fetcher.py`
- `sources/pdf_renderer.py`
- `sources/management/commands/adhoc_fetch.py`
- `apps/api/ingest.py`（chain orchestrator）
- `apps/api/ingest_views.py`（3 个 ingest endpoint + `_save_pdf`）
- `apps/api/jobs.py`（in-memory job queue）
- `apps/core/scheduler.py`（APScheduler 单例）
- `apps/core/apps.py`
- `apps/extract/management/commands/extract_paper.py`
- `apps/interpret/management/commands/interpret_paper.py`
- `apps/render/management/commands/render_graph.py`
- `subscriptions/management/commands/run_subscription.py`

参考（只读）：

- `apps/api/views.py`（Trigger / Brief views，job 入队点）
- `apps/api/subscriptions_views.py`（订阅 CRUD + `_do_run_subscription` 包 call_command）
- `apps/api/urls.py`
- `apps/papers/brief_generator.py`（ft-033 桥接）
- `apps/papers/signals.py`（pre_save 桥接 paper FK）
- `sidecar_entry.py`（sidecar 启动）

不在范围（交其它 group）：

- A 组：`interpret/*` 顶层包（legacy LLM / rewriter / ranker / skim/deep）、`delivery/*`、`subscriptions/loader.py / memory.py`、`apps/extract/extractor.py`、`apps/interpret/interpreter.py`、`apps/render/*` 渲染器。
- B 组：DRF view 层 / serializer / `apps.papers.brief_generator` 业务语义、user_* layer。

总计：审了 17 个 C 组文件 + 6 个对照参考；产出 13 条 hotspot、6 条改造提议。

## 2. 双链调用图

### 2.1 旧 email 链（subscription → SMTP）

入口：`subscriptions/management/commands/run_subscription.py:60` `Command.handle`

```
manage.py run_subscription <name>
  └─ subscriptions.loader.load(yaml)                        # YAML
  └─ interpret.rewriter.rewrite()  [LLM]                    # 兴趣→SourceQuery
  └─ for spec in sub.sources:
        sources.base.REGISTRY[spec.key].fetch()             # arxiv / hf_papers
  └─ subscriptions.memory.known_dedup_keys()                # cross-run dedup
  └─ interpret.ranker.rank()       [LLM]
  └─ for it in scored_items:                                # 每篇
        sources.pdf_fetcher.fetch_pdf(it)                   # ★ 共享
        interpret.pdf_chunker.chunk_pdf()
        interpret.caption_extractor.extract_captions()      # ★ legacy
        interpret.figure_picker.pick_*()
        sources.pdf_renderer.render_bbox_to_png()           # ★ 共享
  └─ interpret.interpretation.skim_interpret() [LLM]
  └─ interpret.deep_interpret.deep_interpret_rich() [LLM]   # ★ 共享
  └─ interpret.narrative.build_narrative() [LLM]
  └─ delivery.<channel>.deliver()                           # SMTP / 其它
  └─ subscriptions.memory.append_*()                        # 写记忆
```

异步触发口：`apps/api/subscriptions_views.py:127` `_do_run_subscription` 通过
`jobs.enqueue(call_command(...))` 包一层走 APScheduler。

### 2.2 新 ingest 链（用户手动 → brief + graph）

入口（3 个 view 都收敛到同一 chain）：
- `apps/api/ingest_views.py:63` `IngestUploadView.post` — multipart
- `apps/api/ingest_views.py:99` `IngestArxivView.post` — `{arxiv_id}`
- `apps/api/ingest_views.py:139` `IngestUrlView.post` — `{url}`

```
POST /api/ingest/{upload|arxiv|url}/
  └─ _save_pdf(content, paper_id)                           # ingest_views.py:38
        └─ Paper.objects.get_or_create(arxiv_id=...)        # 提前建 Paper 行
  └─ chain_extract_interpret_render(paper_id, pdf_path)     # ingest.py:101
       └─ jobs.enqueue(_chain_body)                         # APScheduler
            └─ _run_extract():   apps.extract.extractor.extract + persist_result
            │     └─ pre_save signal autowire paper_arxiv_id → Paper FK
            │       (apps/papers/signals.py:47)
            └─ _run_interpret(): apps.interpret.interpreter.DefaultInterpreter
            │     └─ DefaultInterpreter 内部 import interpret.llm  ★ 跨链
            └─ _run_render():    apps.render.{graph, excalidraw_renderer, persist}
```

异步入队：DRF view → `apps.api.jobs.enqueue` → APScheduler one-shot job → `_chain_body`。

旁路：`POST /api/papers/<id>/brief/regenerate/` 不走 chain，**同步阻塞**调
`apps.papers.brief_generator.generate_brief`，内部 import `interpret.deep_interpret` /
`interpret.interpretation`（views.py:336–339）。

### 2.3 重叠节点

| 资源 | 旧链 | 新链 | 备注 |
| --- | --- | --- | --- |
| `sources/pdf_fetcher.fetch_pdf / _download / local_pdf_path` | ✓ | ✓ ingest_views.py:115 / brief 间接 | arxiv 下载缓存共用 |
| `sources/pdf_renderer.render_bbox_to_png` | ✓ run_subscription.py:230 | ✗ ingest 链不渲染图（apps/render 是图谱不是 caption 图） | 仅 email 链使用 |
| `apps/core/paths.papers_dir / pdf_legacy_dir` | ✓ | ✓ | 路径根都从这里来 |
| `interpret.llm`（LLM client）| ✓ | ✓ apps/interpret/interpreter.py:13 / llm_client.py:12 import | apps/interpret 没自带 LLM client，复用 legacy |
| `interpret.deep_interpret.deep_interpret_rich` | ✓ | brief_generator.py:191 (旁路链) | 通过 brief 桥接 |
| `interpret.interpretation.skim_interpret` | ✓ | brief_generator.py:192 | 同上 |
| `apps.extract` / `apps.interpret` / `apps.render` 落库 | ingest 链才用 | ingest 链 | run_subscription 不入这些表 |
| `subscriptions.loader / memory` | ✓ | ✓ brief_generator.py:19 读 PerspectiveSpec | 仅读 yaml，不写 |
| `apps.api.jobs / apps.core.scheduler` | ✓ subscriptions_views.py:156 | ✓ ingest.py:115 / views.py:518/531/549 | 共享 in-memory queue |
| `sources.base.REGISTRY / Item / SourceQuery` | ✓ | brief_generator.py:18 仅复用 `Item` 数据类 | 新链不走 fetcher |

**结论**：新 ingest 链和旧 email 链在"PDF 抓取 + LLM 客户端 + chunk/caption/deep
interpret 工具集"上深度共享；归并的实质阻力不在公共件上，而在
（a）`apps/interpret/interpreter.py` 走 L1+L2 catalog 路线、
`interpret/interpretation.py` 走 skim/deep 路线，**两套 prompt + 两套结果模型并存**；
（b）旧链有 narrative / ranker / memory 这些 ingest 不需要的步骤。归并方向应是
"ingest 链 = 旧链的子图（裁掉 fetcher / ranker / narrative / delivery）"，统一到
同一组 step 抽象上。详见 §6。

## 3. 耦合 hotspot（最多 15 条）

严重度：1 = 写死或必坏；2 = 设计债，影响 ft-034；3 = 待清理但能跑。

| # | 标题 | 文件:行 | 严重度 | 工时 | 阻 ft-034 |
|---|---|---|---|---|---|
| H1 | **chain orchestrator 与 trigger view 三步函数完全重复** | `apps/api/ingest.py:22-57` vs `apps/api/views.py:481-512` | 1 | 0.5d | yes |
| H2 | **chain 控制流是硬编码 imperative**，不能跳过/重做某阶段 | `apps/api/ingest.py:60-98` | 2 | 1.5d | yes |
| H3 | **新链 lazy import legacy `interpret.llm`** | `apps/interpret/interpreter.py:13`、`apps/interpret/llm_client.py:12` | 1 | 1d（迁 client） | yes |
| H4 | **brief_generator 函数体内 lazy import 老链** 跨"解读 vs 解压"两条路 | `apps/papers/brief_generator.py:191-192`、`apps/api/views.py:336-339` | 2 | 1d | yes |
| H5 | **APScheduler 单例无人启停**：sidecar 进程退出无 hook，依赖 jobs.py:113 lazy 启动 | `apps/core/scheduler.py:42-62`、`sidecar_entry.py:104-135` | 2 | 0.5d | no |
| H6 | **in-memory `_JOBS` dict 进程重启即丢**——sidecar 重启后前端轮询 404 | `apps/api/jobs.py:51-52` | 2 | 1d（落 SQLite job 表） | partial |
| H7 | **brief regenerate 同步阻塞** view，5–15s 不入 jobs queue | `apps/api/views.py:333-348` | 2 | 0.5d | yes |
| H8 | **REGISTRY 注册靠 side-effect import**——`sources/fetchers/__init__.py` 仅在 run_subscription / adhoc_fetch 触发；新链 + ingest_views 直接 import `sources.pdf_fetcher`，REGISTRY 永远空 | `sources/fetchers/__init__.py:1-2`、`subscriptions/management/commands/run_subscription.py:39` | 3 | 0.2d（apps.core.apps.ready 里 import 一次） | no |
| H9 | **ingest_views 绕过 REGISTRY 直接调 `sources.pdf_fetcher._download`**（私有名）做 arxiv 下载 | `apps/api/ingest_views.py:115-127` | 2 | 0.5d（提升为 `fetch_pdf_by_id` 公共 API） | yes |
| H10 | **路径硬编码 `BASE_DIR/'media'/'pdf'`** 在 management commands 里——违反 ft-022 EXPLORE_OS_DATA_DIR 约束，frozen exe 中不可写 | `apps/extract/management/commands/extract_paper.py:32`、`apps/interpret/management/commands/interpret_paper.py:32` | 1 | 0.2d（改 `paths.papers_dir()`） | no |
| H11 | **`_save_pdf` 在 view 里打 ORM**（`Paper.objects.get_or_create`）创业务实体 | `apps/api/ingest_views.py:50-58` | 3 | 0.3d（挪到 `apps.papers.services`） | no |
| H12 | **subscriptions_views 走 `call_command` 包 management command**——绕开 chain 抽象，stdout/stderr tail 当结果用 | `apps/api/subscriptions_views.py:127-142` | 2 | 1d（拆 run_subscription handle 为可调函数） | partial |
| H13 | **fetcher 注册顺序敏感**：`sources/fetchers/__init__.py:1-2` 决定 REGISTRY iter 顺序；测试里 `del REGISTRY[...]` 靠手工恢复（见 sources/tests_*） | `sources/fetchers/__init__.py:1-2`、`sources/base.py:73` | 3 | 0.5d（引入 entry-points 或 explicit register fn） | no |
| H14 | **render fmt 默认值 "excalidraw" 在三处复制**：ingest.py:39、views.py:496/543、render_graph.py:25。改默认值要扫三处 | `apps/api/ingest.py:39`、`apps/api/views.py:496`、`apps/render/management/commands/render_graph.py:25` | 3 | 0.1d | no |
| H15 | **stage 失败错误透传只用 RuntimeError + str**，丢掉原 traceback 类型——前端无法区分网络错 / LLM 错 / docling 错 | `apps/api/ingest.py:79-92` | 3 | 0.3d（保留 `__cause__` chain + 错误码） | yes |

最严重三条：**H1**（双套 chain 函数 = ft-034 单一 orchestrator 强阻塞）、**H3**（apps/interpret 反向 import legacy `interpret.*` = 解耦无法做）、**H10**（hardcoded `BASE_DIR/media` = sidecar 打包后崩）。

## 4. 死/活 management commands 清单

仅项目自定义命令，不含 Django/DRF 自带。

| 路径 | 调用方式 | 状态 | 证据 |
|---|---|---|---|
| `subscriptions/management/commands/run_subscription.py` | DRF `_do_run_subscription` 走 `call_command` + 用户手 CLI | **活** | `apps/api/subscriptions_views.py:134-137` `call_command("run_subscription", name, yaml=...)` 是唯一从生产代码触发 management command 的点 |
| `sources/management/commands/adhoc_fetch.py` | 手 CLI（开发联调 fetcher） | **疑** | grep 全仓无 `call_command("adhoc_fetch", ...)` 任何调用方；docstring 自陈"仅用于实战验证（ft-003 / ft-004）"。当前阶段是 dev tool，桌面 app 打包后不暴露 |
| `apps/extract/management/commands/extract_paper.py` | 手 CLI（dev 调试） | **疑/重复** | 全仓无 `call_command("extract_paper", ...)`；与 `views._do_extract` (views.py:481) + `ingest._run_extract` (ingest.py:22) 实现完全重叠（H1）。生产入口走 `jobs.enqueue(_do_extract, ...)`，CLI 仅 dev fallback |
| `apps/interpret/management/commands/interpret_paper.py` | 手 CLI（dev 调试） | **疑/重复** | 同上：`call_command("interpret_paper")` 0 处；与 `views._do_interpret` + `ingest._run_interpret` 三套实现一致 |
| `apps/render/management/commands/render_graph.py` | 手 CLI（dev 调试） | **疑/重复** | 同上：`call_command("render_graph")` 0 处；与 `views._do_render` + `ingest._run_render` 三套实现一致 |

**结论**：仅 `run_subscription` 是生产链路真正调用的 command。其它 4 个**全部是 dev-only CLI**，且 extract/interpret/render 三个还是 chain 函数的复读机——若 ft-034 把 chain 抽象统一，这 3 个 command 应该改成 thin wrapper（`call chain.run_extract(...)`）而非各自重新 import + run + persist。`adhoc_fetch` 在桌面 app 形态下没有产品价值，建议挪到 `scripts/` 或保留供 ft-040+ debug。

## 5. APScheduler 集成评估

| 维度 | 现状 | 风险 |
|---|---|---|
| **单例** | `apps/core/scheduler.py:24` 模块级 `_SCHEDULER` + double-checked locking，进程内单例 | OK；多 worker 场景（waitress threads=8）共享同一 scheduler，APScheduler 自身线程安全 |
| **启动时机** | **lazy**：`apps/api/jobs.py:113` `start_scheduler()` 在首个 `enqueue()` 时触发；sidecar_entry.py 不主动启 | 首次 ingest 请求会多 ~50ms 启动开销；冷启动阶段若有 cron 类需求**会丢**（目前无 cron） |
| **进程退出清理** | **无**。`shutdown_scheduler` 只在 pytest fixture 调用，sidecar_entry.py 没注册 atexit / signal handler | Electron kill 子进程时 background scheduler 内 in-flight job 直接被切。SQLite 连接可能未 commit；落库 partial state |
| **失败重试** | `add_job` 设 `misfire_grace_time=60` 但**未配置 retry**；`_wrap` 捕获异常仅记 status=failed | 网络瞬抖打偏 LLM call 直接整链 fail，没有 stage-level retry。tenacity 仅在 `sources.pdf_fetcher._download` (3 次指数退避) |
| **持久化** | **零持久化**：APScheduler 默认 MemoryJobStore + `_JOBS` in-memory dict | 进程重启所有 queued/running job 丢失；前端轮询 `/jobs/<id>` 返 404；H6 |
| **多 source 派发** | run_subscription 内部 for 循环串行 `fetcher.fetch(...)` (run_subscription.py:110-141)；未通过 scheduler 并行 | 5 sources × 2s ≈ 10s 串行延迟；可改 `add_job` 多 worker 但当前线性 |
| **job 注册点** | enqueue 处共 5 个：`apps/api/ingest.py:115`、`views.py:518/531/549`、`subscriptions_views.py:156` | 无统一注册中心；要绑 ft-034 chain 必须收敛到一个 `chain.dispatch()` |
| **cron / 周期任务** | `register_default_jobs()` 是空函数（scheduler.py:65-71），桌面 app 形态下没有定时跑订阅 | 长期形态承诺"APScheduler in-process 不依赖外部 cron"——这条目前**未兑现**。CLAUDE.md 自陈"v1.1 起" |
| **timezone** | hardcoded `Asia/Shanghai`（scheduler.py:37） | 海外用户 cron 时间会偏 |

**改造优先级**（与 ft-034 配套）：
1. sidecar_entry.py 启动时显式 `start_scheduler()` + `register_default_jobs()` + atexit `shutdown_scheduler(wait=True)`（H5）。
2. `_JOBS` 落 SQLite job 表（H6），同时让 APScheduler 用 SQLAlchemyJobStore 指向同一 DB。
3. job_id 与 chain stage 解耦：每个 stage 独立可查（前端能展示 extract ✓/interpret ⏳/render queued）。
4. cron 注册接口落地——`register_default_jobs()` 读 `subscriptions.yaml`，每个 enabled sub 自动建 cron job。

## 6. 解耦改造提议（最多 10 条）

按 ft-034 优先级排。

### P1 — 拆 chain 抽象层（核心，吃掉 H1/H2/H15）
- 现状：`ingest._run_extract / _run_interpret / _run_render` 与 `views._do_extract / _do_interpret / _do_render` 完全重复；orchestrator 是 imperative if/try。
- 建议：抽 `apps/core/chain.py`，定义 `Stage(name, fn, persist_fn)` + `Pipeline([s1, s2, s3]).run(ctx) -> StageResult` 协议；让 `ingest.py` 和 trigger views 都从同一处取 stage 列表。错误透传保留原 exception type。
- 工作量：1d
- 风险：测试需要重写（tests_ingest / tests_views 大改）

### P2 — apps.interpret 自带 LLM client，剪 legacy import（吃 H3）
- 现状：`apps/interpret/llm_client.py:12` `from interpret.llm import LLMError, chat, extract_json`，新链反向依赖 legacy 顶级 `interpret/`。
- 建议：把 `interpret/llm.py` 的 chat + extract_json 提到 `apps/core/llm_client.py`（A 组也提了类似建议）；`apps/interpret/llm_client.py` 与 legacy `interpret.interpretation` 都改为 import 新位置。
- 工作量：0.5d
- 风险：低；纯 import 重定向

### P3 — brief_generator 走 chain，砍掉对 legacy 函数的 lazy import（吃 H4）
- 现状：`brief_generator.py:191-192` 在函数体内 `from interpret.deep_interpret/interpretation import ...`；导致 brief = "解读" 路径绕过 ft-034 chain。
- 建议：deep_interpret_rich / skim_interpret 也作为 stage 注册到 chain；brief = run pipeline with `stages=["skim", "deep"]`。
- 工作量：1d（绑 P1）
- 风险：要确认 brief 不需要 `apps.interpret` 那套 catalog/L1/L2，是另一组 prompt

### P4 — jobs queue 落 SQLite + scheduler 进程级生命周期（吃 H5/H6）
- 现状：`_JOBS` in-memory；scheduler 无人启停。
- 建议：建 `apps.core.models.Job(job_id, name, status, started_at, finished_at, result_json, error)`；jobs.py 改读写这张表；APScheduler 切 SQLAlchemyJobStore。sidecar_entry.py 显式 start + atexit shutdown。
- 工作量：1d
- 风险：测试需要 db fixture；in-flight job 重启策略要拍板（resume vs mark-as-failed）

### P5 — `_save_pdf` 挪出 view 层 + REGISTRY 注册改到 AppConfig.ready（吃 H8/H11）
- 现状：业务逻辑（建 Paper 行）写在 view；REGISTRY 注册靠 caller 记得 import sources.fetchers。
- 建议：建 `apps.papers.services.save_pdf_for_paper(content, paper_id) -> Path`；fetcher 注册放 `sources.apps.SourcesConfig.ready()`（需建 AppConfig）。
- 工作量：0.5d
- 风险：低

### P6 — 路径走 `paths.papers_dir()`，砍 BASE_DIR/'media' hardcode（吃 H10）
- 现状：3 个 management command 用 `Path(settings.BASE_DIR) / "media" / "pdf"`。
- 建议：`from apps.core.paths import papers_dir` + `papers_dir() / f"{arxiv_id}.pdf"`。
- 工作量：0.2d
- 风险：零；CLI 行为不变

### P7 — brief regenerate 入 jobs queue（吃 H7）
- 现状：`PaperBriefRegenerateView.post` 同步阻塞 5–15s。
- 建议：`info = jobs.enqueue(generate_brief, paper.id, regenerate=True)`，返 202 + job_id。前端轮询。
- 工作量：0.5d
- 风险：低；前端需要小改 loading 态。绑 P3 后 brief 走 chain 更顺。

### P8 — pdf_fetcher 公开 by-id API（吃 H9）
- 现状：ingest_views 直接调 `_download` 私有名。
- 建议：sources.pdf_fetcher 加 `fetch_pdf_by_id(arxiv_id) -> Path`，ingest_views 走这个公开 API。同时 `sources.fetchers` 模块自动 register on AppConfig.ready。
- 工作量：0.3d
- 风险：零

### P9 — chain stage error 保留 exception 类型（吃 H15）
- 现状：`raise RuntimeError(f"extract failed: {exc}") from exc` 把 docling/LLM/网络错都拍平成 RuntimeError。
- 建议：定义 `StageError(stage_name, original_exc, retryable: bool)`，前端能显示"网络错可重试"vs "PDF 损坏不可重试"。
- 工作量：0.3d
- 风险：低；绑 P1

### P10 — run_subscription handle 拆为可调函数（吃 H12）
- 现状：subscriptions_views `_do_run_subscription` 走 call_command + capture stdout，结果通过 `stdout_tail` 字符串返回——前端解析痛苦，错误结构不可机读。
- 建议：把 `Command.handle` 主体抽为 `subscriptions.runner.run(name, *, dry_run=False, ...) -> RunResult` 数据类；management command + DRF 都调它。
- 工作量：1d
- 风险：中；测试覆盖要补

## 7. 不在范围 / 移交其它 group

审阅过程中发现的越界问题，按 group 标注移交：

### 移交 A 组（interpret / delivery / subscriptions 业务）
- **A-1**：`interpret/llm.py` 是 legacy LLM client 的事实上的"公共"实现，被 `apps/interpret/llm_client.py:12` 反向依赖。建议 A 组把 chat/extract_json 抽到 `apps/core/llm_client.py`，让两套 interpret 实现都走新位置（与本组 P2 配套）。
- **A-2**：`interpret/interpretation.py` (skim/deep) 与 `apps/interpret/interpreter.py` (L1+L2) **两套 prompt + 两套结果模型**并存。是否归并需 A 组拍板：当前 brief 用前者、graph 用后者，能否统一一组结构化 schema？这是 ft-034 chain 抽象成立的前提之一。
- **A-3**：`subscriptions/loader.py` `_resolve_perspective`-style 读 yaml 的代码在 brief_generator.py 也复制了一份（见 brief_generator.py:19 周边），建议 A 组拉一个 `subscriptions.perspective.resolve()` 给两边复用。

### 移交 B 组（DRF view 层 / serializer / user_* layer）
- **B-1**（与本组 H7 重复）：`PaperBriefRegenerateView` 同步阻塞，view 层超时风险。本组提了 P7（入 jobs queue），实施权在 B 组。
- **B-2**：`apps/api/views.py:481-512` 的 `_do_extract / _do_interpret / _do_render` 严格说是 view 层模块组织问题——应不应该把 trigger handler 抽到 `apps/api/triggers.py` 单独管。本组只指出复制（H1），具体 view 层重构方案 B 组定。
- **B-3**：`_save_pdf` 在 ingest_views.py 直接打 `Paper.objects.get_or_create` ORM——这是 view 层 vs services 层边界问题（本组 H11/P5），由 B 组评估。

### 移交 D 组（前端 / Electron）
- **D-1**：jobs 落 SQLite 后（P4），前端 `/api/jobs/<id>` 轮询 contract 不变（仍是 JobInfo dict），但需要支持 `progress: {stage, percent}` 字段以便展示 chain 进度。需 D 组确认 UX。
- **D-2**：Electron 主进程 kill sidecar 时如何 graceful shutdown scheduler——需要 D 组在 main process 发 SIGTERM 而非 SIGKILL，sidecar 监听信号调 `shutdown_scheduler(wait=True)`。绑 P4。

### 移交 E 组（运维 / 打包 / sidecar）
- **E-1**：sidecar_entry.py 应在 `django.setup()` 后、`server.run()` 前调 `start_scheduler()` + `register_default_jobs()`；并在 server.run() 外层 try/finally 调 `shutdown_scheduler(wait=True)`。绑本组 P4 / H5。
- **E-2**：`scheduler.py:37` `timezone="Asia/Shanghai"` hardcoded——E 组打包配置应支持读环境变量 `EXPLORE_OS_TZ` 或 OS locale。
- **E-3**：APScheduler `BackgroundScheduler` 与 waitress threads=8 共存的线程模型未做压测——E 组建议在 v1.0 release 前跑一次 8 并发 ingest 压测验证 SQLite 锁行为。

### 移交 F 组（测试 / CI）
- **F-1**：`apps/core/tests_scheduler.py` 测了 idempotent start/shutdown，但没测"shutdown 时有 pending job 怎么办"——F 组应补 in-flight job 中断策略测试。
- **F-2**：当前 chain 测试在 `apps/api/tests_ingest.py` 走 `inline=True` 路径，没覆盖真 background scheduler 路径。F 组建议补 e2e 测试（pytest fixture + threading event）验证 async 链路。
- **F-3**：`sources/tests_*` 通过 `del REGISTRY[key]` 手工恢复测试隔离——脆。F 组可统一一个 `registry_isolation` fixture（绑本组 H13）。

---

**review-C-pipeline 完。** 总结：双链可在 ft-034 收敛，但前提是 A 组先解决 prompt/schema 二元化（A-2），否则只是把"两条路"打包成"两条 stage list"。本组提议 P1+P2+P4 是 ft-034 必做项；P3/P7 是 brief 路径并入 chain 的必要条件；P5/P6/P8/P9/P10 是清洁工作可分批落。
