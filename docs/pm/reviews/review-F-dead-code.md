---
review_id: review-F-dead-code
review_group: F
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---

# Review F — 死码 / 重复实现 / 测试覆盖空洞

## 1. 范围确认

**扫描目录**：`apps/`（6 个 Django app）、`interpret/`（顶级 legacy）、`sources/`（顶级抓取层）、
`subscriptions/`、`delivery/`、`config/`、`frontend/src/`、`electron/src/`、根级 `*.py`。

**排除**：`docs/`、`__pycache__`、`node_modules`、`build`、`dist-electron`、Django migrations、
`uv.lock`。

**Python 文件计数**（关键目录，不含 migrations）：

- `interpret/` 顶级 legacy：18 文件 / 1 891 行（含 stub `admin.py` `models.py` `tests.py` 各 0 行）
- `apps/extract/`：12 文件 / 1 729 行（含 extractors/）
- `apps/interpret/`：12 文件 / 1 088 行
- `apps/render/`：12 文件 / 1 444 行
- `sources/`：11 文件 / 1 197 行
- `apps/api/`：14 文件
- `frontend/src/`：6 个 api / 17 个 component / 6 个 page / 1 store / 1 hook

**取证方法**：每模块顶层 grep `from interpret\.<X>` `from apps\.<x>` 引用，排除自身 + `tests_*.py` +
`docs/*.md` 后计数。`call_command(...)` 全仓 grep 仅 1 处（`sidecar_entry.py:102` 调 migrate）+
1 处（`apps/api/subscriptions_views.py:135` 调 `run_subscription`）。

## 2. 死码清单（按删除安全度 A/B/C 分组，上限 30 条）

A=立刻删（业务零引用，仅自身 + tests）；B=需 shim/迁移（有零星调用方，迁完即删）；
C=保留待定（依赖未切清/语义不确定）。

### A 类（可立刻删，11 项）

| # | 文件:行号 | 业务引用计数 | 取证 |
|---|---|---|---|
| A1 | `interpret/tldr.py` (51 行) | 0 | grep `from interpret\.tldr` 全仓无业务匹配；review-A 已确认 |
| A2 | `interpret/figure_classifier.py` (105 行) | 0 | 业务无 import；只 `tests_figure_classifier.py:6` self；review-A H12 已锁 |
| A3 | `interpret/tests_figure_classifier.py` (102 行) | — | 跟 A2 同生死 |
| A4 | `interpret/admin.py` (0 行 stub) | — | 文件 0 字节，无 model 配置必要（顶级 `interpret/` 已无 model） |
| A5 | `interpret/models.py` (0 行 stub) | — | 0 字节；`interpret/migrations/` 仅含 `__init__.py`（0 migration），ORM 全在 `apps/{extract,interpret,render}/models.py` |
| A6 | `interpret/tests.py` (0 行 stub) | — | 0 字节，pytest 不会跑空 module |
| A7 | `interpret/apps.py` (6 行) + `interpret/__init__.py` + `INSTALLED_APPS` 注册 | — | 整个顶级 `interpret/` 已是"老 LLM 业务函数集 + 3 个 thin wrapper"，无 model/migrations，AppConfig 形同虚设。整 app 改为 plain Python package（移除 `apps.py` + 从 INSTALLED_APPS 摘除）只剩业务函数 |
| A8 | `interpret/management/commands/` 空目录（仅 `__init__.py`） | — | 顶级 interpret 没有任何 management command 文件 |
| A9 | `sources/admin.py` (0 行 stub) | — | 0 字节 stub，无 admin 注册 |
| A10 | `sources/models.py` (0 行 stub) | — | 0 字节 stub；`sources/` 不持久化（fetch 后由 `apps.papers` 落库） |
| A11 | `sources/tests.py` (0 行 stub) | — | 0 字节，pytest 抓不到 |

> 注：A4-A11 的 stub 文件每个都是 0 字节但仍占文件位 + IDE 索引；批量清理零成本。

### B 类（需 deprecation shim 或迁移，6 项）

| # | 文件 | 计数 | 阻碍 |
|---|---|---|---|
| B1 | `interpret/caption_extractor.py` (14 行 thin re-export) | 业务 1 处 (`subscriptions/management/commands/run_subscription.py:26`) + 测试 2 处 | 改 `run_subscription` 为 `from apps.extract.caption_extractor import ...` 后即删 |
| B2 | `interpret/figure_extractor.py` (18 行 thin re-export) | 业务 2 处 (`run_subscription.py:28` + `interpret/figure_classifier.py:12`) | A2 删完后只剩 1 处 → 改 import → 删 |
| B3 | `interpret/pdf_chunker.py` (17 行 thin re-export) | 业务 2 处 (`interpret/deep_interpret.py:18` + `run_subscription.py:36`) + 测试 2 处 | 改两处 import 即可删 |
| B4 | `apps/extract/management/commands/extract_paper.py` (48 行) | 0 `call_command`，与 `apps/api/ingest._run_extract` 100% 重复 | 工程师 CLI 试跑用；可保留但应在 docstring 标注"调试用，生产走 `chain_extract_interpret_render`" |
| B5 | `apps/interpret/management/commands/interpret_paper.py` (46 行) | 0 `call_command`，与 `_run_interpret` 100% 重复 | 同 B4 |
| B6 | `apps/render/management/commands/render_graph.py` (66 行) | 0 `call_command`，与 `_run_render` 100% 重复 | 同 B4 |

### C 类（待定，4 项）

| # | 文件 | 怀疑 | 待澄清 |
|---|---|---|---|
| C1 | `interpret/embedding.py` (91 行) | 仅 `interpret/ranker.py:?` + `tests_*` 引用 | `ranker.rank()` 还被 `run_subscription.py:37` 调用 → embedding 间接活，但 ft-028 后是否还有效？ |
| C2 | `interpret/narrative.py` (82 行) | 业务 3 处：`run_subscription.py:35` + `delivery/base.py:14` + `delivery/adapters/email.py:31` | E 组（delivery）规划中切新注册表；切完才能删；现状仍活 |
| C3 | `interpret/figure_picker.py` (160 行) | 业务 1 处：`run_subscription.py:29` | ft-019 文档说"暂不动，ft-020 处理"，ft-020 已结束未动 → 半 deprecated 但仍被 email 链调用 |
| C4 | `interpret/rewriter.py` (75 行) | 业务 1 处：`run_subscription.py:38` | rewriter 还活但只 1 入口；email 链一旦砍，rewriter 整模块死 |

## 3. 重复实现清单（上限 10 条）

| # | 能力 | 实现 A | 实现 B | 状态 |
|---|---|---|---|---|
| D1 | LLM HTTP chat client | `interpret/llm.py` (118 行) — 唯一真正的 HTTP `chat()` + `extract_json()` | `apps/interpret/llm_client.py:12 from interpret.llm import LLMError, chat, extract_json` — 只多套 `chat_json()` JSON-only 包装 | A=源 / B=封装；B 不是重复实现而是 thin wrapper（OK），但 `apps/interpret/interpreter.py:13 from interpret.llm import LLMError` 是绕过 B 直引 A — 应统一走 B |
| D2 | PDF section/chunk 解析 | `apps/extract/section_extractor.py` (170 行) | `interpret/pdf_chunker.py` (17 行 thin re-export) | B 是 wrapper，不是真重复；调用方仍走 B（`run_subscription.py:36` + `deep_interpret.py:18`），实现已统一在 A |
| D3 | Caption 抽取 | `apps/extract/caption_extractor.py` (328 行) | `interpret/caption_extractor.py` (14 行 thin re-export) | 同 D2，B wrapper 仅留兼容，A 是源 |
| D4 | Figure 抽取 | `apps/extract/figure_extractor.py` (194 行) | `interpret/figure_extractor.py` (18 行 thin re-export) | 同 D2 |
| D5 | 单 paper 三阶段 pipeline | `apps/api/ingest._run_extract / _run_interpret / _run_render` (ingest.py:22-57) — chain function | `apps/{extract,interpret,render}/management/commands/{extract_paper,interpret_paper,render_graph}.py` — 各 46-66 行 management command | A 是新链；B 三个 command 调用同样的 `extract / persist_result` / `DefaultInterpreter` / `build_graph + persist_artifact` 但加 CLI argparse 包装。重复逻辑约 100 行；call_command 0 处 |
| D6 | apps/api `_do_extract` / `_do_interpret` / `_do_render` | `apps/api/views.py:481-512` 函数定义 | `apps/api/ingest._run_*` (ingest.py:22-57) | views.py 三个 `_do_*` 仅 cosmetic 包装 `apps.{extract,interpret,render}` 的 entrypoint — 与 ingest.py 三个 `_run_*` 几乎逐字重复，存在第二组同名函数 |
| D7 | brief 生成内的 import 反向依赖 | `apps/papers/brief_generator.py:191-192` 函数体内惰性 `from interpret.deep_interpret import deep_interpret_rich` / `from interpret.interpretation import skim_interpret` | 新链 `apps/interpret/interpreter.py` `DefaultInterpreter` (L1+L2) | 两条解读路径（brief = 老 skim/deep；ingest = L1+L2 claim）共存且都活，构成功能重复（同样产出"对论文的 LLM 理解"），见 review-A H2 / review-C H1 |
| D8 | LLM prompt 模板 | `interpret/{tldr,interpretation,deep_interpret,narrative,rewriter,figure_picker,figure_classifier}.py` 各自定义 SYSTEM 字符串 | `apps/interpret/prompts.py:65` (L1_SYSTEM/L2_SYSTEM) | 老 7 处分散 vs 新 1 处集中；review-A H3 已锁；prompt 治理散点 |
| D9 | `delivery/email_renderer.py` (5 行 wrapper) + `delivery/email_sender.py` (21 行 wrapper) | 实际实现 `delivery/adapters/email.py` (451 行) | 两个 wrapper 自承"Backwards-compatible thin wrapper" | grep `email_sender|email_renderer` 业务全仓 0 处真正调用（仅 `from delivery.adapters.email import _send_smtp` 在 wrapper 自身用），可清 |
| D10 | `interpret/management/commands/` 空目录 | 实质 0 commands | — | 应清整个目录 |

## 4. superseded 模块（新→旧映射）

## 4. superseded 模块（新→旧映射）

按能力维度梳理"新位置 ← 老位置"，每行注明老位置当前是否仍活。

| 新（保留） | 老（superseded） | 老位置状态 | 阻塞老删除的最后一个调用方 |
|---|---|---|---|
| `apps/extract/caption_extractor.py` | `interpret/caption_extractor.py` (wrapper) | 半死 | `run_subscription.py:26` |
| `apps/extract/figure_extractor.py` | `interpret/figure_extractor.py` (wrapper) | 半死 | `run_subscription.py:28` + `interpret/figure_classifier.py:12` |
| `apps/extract/section_extractor.py` | `interpret/pdf_chunker.py` (wrapper) | 半死 | `run_subscription.py:36` + `interpret/deep_interpret.py:18` |
| `apps/interpret/llm_client.py:chat_json` | `interpret/llm.py:chat` | 必须保留（B 仍以 A 为底） | `apps/interpret/{interpreter.py:13, llm_client.py:12}` + 老 7 模块 + tests |
| `apps/interpret/interpreter.py:DefaultInterpreter` (L1+L2 claims) | `interpret/interpretation.py:skim_interpret` + `interpret/deep_interpret.py:deep_interpret_rich` | 仍活（brief_generator + run_subscription + email 链） | `apps/papers/brief_generator.py:191-192` + `delivery/{base,adapters/email}.py` + `subscriptions/management/commands/run_subscription.py` |
| `apps/interpret/prompts.py` (集中 prompt) | 7 处分散 SYSTEM 字符串 | 老仍活 | 同上（解读链未切就还在用老 prompt） |
| `apps/papers/models.Paper` FK 关联 | `paper_arxiv_id` 字符串字段 | 仍是混合状态 | `apps/render/*` 仍按 arxiv_id 关联（review-C 已述）；非死码，但反映迁移未完 |
| `apps/api/ingest.chain_extract_interpret_render` (新链) | `subscriptions/management/commands/run_subscription.py` (老 email pipeline) | 双活 | 两条管道并存：新链解读 = L1+L2 claim；老链 = TL;DR+skim+deep+narrative+ranker+rewriter |
| `delivery/adapters/email.py` (含 render_html + _send_smtp) | `delivery/email_renderer.py` + `delivery/email_sender.py` (各 5 / 21 行 wrapper) | wrapper 业务 0 引用 | 可立删 |
| `apps/extract/extractors/docling_ext.py` (DoclingExtractor) | 无老位置 | — | 新写，无 superseded |
| `apps/render/{excalidraw_renderer,svg_renderer,layout,graph,equation_render}.py` | 无 — | — | tldraw / drawio renderer 未引入即弃；非 superseded |

## 5. 测试空洞清单（上限 15 条）

打分维度：模块行数、是否生产入口、出问题影响面。下表按"严重度"降序，T1 = 必补，T2 = 应补，T3 = 可补。

| # | 缺测模块 | 行 | 业务定位 | 现有间接覆盖 | 严重度 |
|---|---|---|---|---|---|
| T1 | `subscriptions/management/commands/run_subscription.py` | 436 | 老 email pipeline 唯一入口、subscription cron 实际跑的脚本 | 无（grep 全仓 0 处 `tests_run_subscription*`）。`apps/api/subscriptions_views.py:135` 通过 `call_command` 异步触发它 — 但调用方测的是 enqueue，不是 command body | T1 |
| T2 | `subscriptions/loader.py` | 139 | YAML → SubscriptionSpec 解析 + PerspectiveSpec；多处 import（brief_generator / run_subscription / api/subscriptions_views） | 无 `tests_loader.py`；`tests_memory.py` 是另一文件 | T1 |
| T3 | `apps/papers/signals.py` | 69 | pre_save 桥接 `paper_arxiv_id` → Paper FK；6 个 model + UserPaperStatus 触发器 | 无；review-A H10 已批"任何新 material 表都需修这里，隐式耦合" | T1 |
| T4 | `apps/api/subscriptions_views.py` | 163 | DRF 视图 + `_do_run_subscription` job worker | 无 `tests_subscriptions_views.py` | T1 |
| T5 | `apps/api/serializers.py` | 184 | 17 个 Serializer 类（PaperList / Brief / Subscription / Backlink ...） | 间接通过 `tests_views.py` `tests_papers.py` 触发，但无字段级直测 | T2 |
| T6 | `sidecar_entry.py` | 140 | Electron sidecar HTTP server 启动入口；migrate / port 选取 / lifecycle | 无；本地启动手测 | T2 |
| T7 | `apps/render/equation_render.py` | 114 | LaTeX → PNG 渲染；缓存命中逻辑 | 无 `tests_equation_render.py`；只在 `tests_excalidraw.py` 间接触发 | T2 |
| T8 | `apps/render/layout.py` | 67 | 布局算法（cluster cards 坐标计算） | `tests_excalidraw.py` 间接触发 | T3 |
| T9 | `apps/papers/paths.py` | 37 | paper 目录解析 helpers | 无；`apps/core/tests_paths.py` 测的是 core/paths | T3 |
| T10 | `delivery/adapters/email.py` | 451 | render_html / _send_smtp / EmailAdapter | `tests_email_adapter.py:render_html` 仅测渲染分支；SMTP 路径 + cid 嵌图无测 | T2 |
| T11 | `interpret/llm.py` | 118 | HTTP chat client + extract_json + retry | 无 `tests_llm.py`（被 7 个老业务模块的 tests 间接 monkeypatch） | T3（老链；新链已用 `apps/interpret/llm_client`） |
| T12 | `interpret/figure_picker.py` | 160 | 架构图选取（规则 + LLM 兜底） | `tests_figure_picker.py:163` 行覆盖良好 | — |
| T13 | `apps/extract/management/commands/extract_paper.py` | 48 | CLI wrapper | 无；与 `_run_extract` 重复（D5）— 删之即无需测 | T3 |
| T14 | `apps/interpret/management/commands/interpret_paper.py` | 46 | CLI wrapper | 同 T13 | T3 |
| T15 | `apps/render/management/commands/render_graph.py` | 66 | CLI wrapper | 同 T13 | T3 |

> 关键发现：**最大产线代码（`run_subscription.py` 436 行）零测试**。一旦 ft-034 chain 切换 / 新解读链替换老链，无测网兜底。建议 iter-019 先补 T1-T3 三个 critical（信号桥接 / loader / pipeline body）。

## 6. 删除路线图

按"无依赖 → 强依赖"顺序，三阶段清理。每步后建议跑 `pytest -q` 全量。

### Phase 1：零阻力（独立小时；不破契约）

| 步骤 | 改动 | 风险 |
|---|---|---|
| 1.1 | 删 `interpret/admin.py` `interpret/models.py` `interpret/tests.py` `sources/admin.py` `sources/models.py` `sources/tests.py`（A4-A6 / A9-A11 全 0 字节 stub） | 无：Django 自动 fallback；migrations 无影响 |
| 1.2 | 删 `interpret/management/` 空目录（A8） | 无 |
| 1.3 | 删 `interpret/tldr.py` + 相关 tests（A1） | 无业务调用方 |
| 1.4 | 删 `delivery/email_renderer.py` + `delivery/email_sender.py`（D9 wrapper 0 引用） | 无；wrapper 已自承"Backwards-compatible" 但 grep 0 调用方 |
| 1.5 | 删 `interpret/figure_classifier.py` + `tests_figure_classifier.py`（A2-A3） | 间接释放 `figure_extractor.py` wrapper 的 1/2 个调用方 |

合计：约 -300 行代码，0 测试改动（删除的测试随同删）。

### Phase 2：thin re-export wrapper 清理（约半天）

| 步骤 | 改动 | 风险 |
|---|---|---|
| 2.1 | 把 `interpret/deep_interpret.py:18 from interpret.pdf_chunker` 改为 `from apps.extract.section_extractor import PaperChunks`；同改 `run_subscription.py:36` | 测试 `interpret/tests_deep_interpret.py` 行 11 有 `from interpret.pdf_chunker import PaperChunks, Section` 需改 |
| 2.2 | 把 `run_subscription.py:26 from interpret.caption_extractor import Caption, extract_captions` → `from apps.extract.caption_extractor import ...` | tests 同步 |
| 2.3 | 把 `run_subscription.py:28 from interpret.figure_extractor import figures_root` → `from apps.extract.figure_extractor import figures_root` | 同 |
| 2.4 | 删 `interpret/{caption_extractor,figure_extractor,pdf_chunker}.py` 三个 wrapper（B1-B3） | 完成 review-A P7 |
| 2.5 | 删 `interpret/tests_{caption_extractor,pdf_chunker}.py`（已迁到 `apps/extract/tests_*`） | 检查覆盖率不下降 |

### Phase 3：解读链统一（review-A H1 / H2 / review-C H1 协同；最大风险）

| 步骤 | 改动 | 风险 |
|---|---|---|
| 3.1 | 把 `interpret/llm.py` 的 `chat / extract_json / LLMError` 搬到 `apps/core/llm_client.py`（review-A H1 提议；review-C H3 也提议）；老 `interpret/llm.py` 改成 thin re-export → 然后整个老链全部改 import | 测试覆盖范围广：7 个老 module + apps/interpret + tests_brief 都需迁移；建议先 import 通；命名不变；不抢工 |
| 3.2 | 决定 brief = "解读" 还是 brief = "skim" 的语义（PM 决定，不在 F 范围）；如果决定 brief 走新链 L1+L2，则砍 `apps/papers/brief_generator.py:191-192` 的反向 import；`interpret/{interpretation,deep_interpret}.py` 的 `skim_interpret` / `deep_interpret_rich` 入口由 brief 切走 | 大改动；review-A H2 + review-C H1 联动 |
| 3.3 | 决定老 email pipeline (`run_subscription.py`) 是否保留：若决定弃，则可清 `interpret/{narrative,ranker,rewriter,figure_picker,interpretation,deep_interpret,embedding}.py` 全部 + `delivery/base.py` 的老 import；若保留则只切 LLM client 不删模块 | 需 PM 拍板"老 email 推送是否仍是产品形态"；当前桌面 app 方向下，email 链是否还需要 |
| 3.4 | 处理 management command 重复（D5）：建议在 docstring 写明"调试 CLI；生产走 chain"；不删（人工试跑仍有价值）。或者改成"thin wrapper 调 ingest._run_extract"以消除逻辑双份 | 低；只是文档标注 |

### Phase 4：测试补全（与 Phase 1-3 并行）

按 §5 T1-T3 顺序补：

1. `subscriptions/loader.py`：YAML 解析 / PerspectiveSpec / SubscriptionSpec 各档位 → ~30 个 testcase
2. `apps/papers/signals.py`：6 个 material 模型 + UserPaperStatus 触发器各 1-2 个 case
3. `subscriptions/management/commands/run_subscription.py`：先做 happy-path 1 case + 各 LLM 失败降级 path

### 风险点与依赖

- Phase 3.3 "是否弃老 email" = 产品决策，不在本 review 范围；F 仅给"可清模块清单"，是否真删由 PM 在 iter-019 分发时决定
- review-A H1 (LLM client 搬迁) 是 phase 3.1 前置；建议合并成一个 commit
- 砍 `interpret/figure_classifier.py` 不阻塞；可独立先做（Phase 1.5）

## 7. 不在范围 / 移交其它 group

| 议题 | 移交 | F 仅指出位置 |
|---|---|---|
| `frontend/src/api/claims.ts` 9 行空壳（D 组确认） | **D 组（frontend）** | 已确认 0 引用方；删除；如需重建 ft-032 再加 |
| `frontend/src/stores/jobsStore.ts` 23 行 vs TanStack Query 重叠 | **D 组** | 实际仍被 4 个组件 `useJobsStore` 调用（`SubscriptionPage` `IngestPage` `ActiveRunsBanner` `useJobPolling`）；非死码，是设计选择（轮询状态显式持有 vs query cache）；不属 F 评判范围 |
| `apps/render/*` 按 `paper_arxiv_id` 字符串关联 | **C 组（pipeline）** | 不是死码而是迁移半成品；F 只在 §4 列入 superseded 表 |
| LLM 客户端两套互依赖 | **A 组（services）H1** | F §3 D1 仅指证 |
| brief vs L1+L2 双解读链 | **A 组 H2 / C 组 H1** | F 不评估"应该哪条留"，只列证据 |
| `delivery/adapters/{feishu,wechat_subscription}.py` stub | **E 组（delivery/UI）** | 不是死码，是 ft-017 / ft-018 故意保留；F 不动 |
| `apps/papers/signals.py:48-56` pre_save 跨 6 model 桥接（review-A H10） | **C 组** | F 仅在 §5 T3 列为测试空洞 |
| `apps/api/views.py` 859 行单文件容量过大 | **B 组（api）** | F 不评结构，仅列 `_do_extract / _do_interpret / _do_render` 与 ingest.py 函数重复（D6）|
| 老 email pipeline 是否弃 | **PM** | F §6 phase 3.3 标决策门 |
| Electron sidecar 入口 `sidecar_entry.py` 缺测 | **E 组** | F §5 T6 仅列 |

## 报告统计

- 扫描 Python 模块：~70 个非测试源文件 + 36 个测试文件
- A 类死码：11 项（含 6 个 stub 0 字节文件）
- B 类（需 shim/迁移）：6 项
- C 类（待定）：4 项
- 重复实现：10 项（含 wrapper 类、CLI 重复、prompt 散点）
- superseded 映射：11 项
- 测试空洞：15 项（T1 critical：3 项）
- **最值得立刻删**：`interpret/tldr.py`（51 行 + tests，0 引用）、`interpret/figure_classifier.py`（105 行 + 102 测试 + 解锁 figure_extractor wrapper）、`delivery/email_renderer.py + email_sender.py`（26 行总，0 业务引用）
- **最大测试空洞**：`subscriptions/management/commands/run_subscription.py` 436 行老 pipeline 全无测试
