---
review_id: review-B-api
review_group: B
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---

# Review B — API 契约层（DRF views / serializers / DTO）

## 1. 范围确认

审了 7 个后端文件（共 1791 行）+ 5 个前端文件（types/paper.ts, api/{papers,claims,ingest,jobs}.ts）：

| 文件 | 行数 | 角色 |
|---|---|---|
| `apps/api/views.py` | 859 | DRF views（papers + user_* + triggers + brief + pdf）—— **巨型 module** |
| `apps/api/urls.py` | 143 | URL routes |
| `apps/api/serializers.py` | 184 | DRF serializers（部分 + 部分纯 Serializer DTO） |
| `apps/api/ingest.py` | 115 | extract→interpret→render chain orchestrator |
| `apps/api/ingest_views.py` | 190 | ingest DRF views（upload/arxiv/url）+ `_save_pdf` 副作用写 Paper |
| `apps/api/subscriptions_views.py` | 163 | Subscription CRUD + run-now |
| `apps/api/jobs.py` | 137 | in-process job queue（APScheduler one-shot 包装） |
| `apps/api/tests_*.py` | only-read | 5 个 test 文件，仅查契约 |

不在本次范围（已移交其它 group，详见 §7）：`apps/papers/brief_generator.py`、`apps/papers/paths.py:resolve_pdf_path`、`apps/extract/*`、`apps/interpret/*`、`apps/render/*`、`apps/core/scheduler.py`、`subscriptions/loader.py`、`sources/pdf_fetcher.py`。

## 2. views.py 结构图

**`apps/api/views.py` 859 行 / 22 个 view class + 6 个 module-level helper**：

| 行号 | 名称 | 职责 |
|---|---|---|
| 51 | `PAPER_KEY_RE` | regex `^[A-Z2-9]{8}$` |
| 54-61 | `resolve_paper(id_or_key)` | ft-028 dispatch：key → arxiv_id 路由 |
| 68-70 | `_default_pdf_path` | legacy `<DATA_DIR>/media/pdf/<id>.pdf` 兜底 |
| 75-85 | `HealthView` GET | scheduler running + data_dir |
| 90 | `_VALID_STATUS_FILTERS` | `{s.value for s in PaperStatus}` |
| 93-203 | `PaperListView` GET | filter（status/tag/q）+ 6 个 count agg + brief join |
| 206-297 | `PaperDetailView` GET | 解析 paper → sections/figures/tables/equations/claims + has_pdf + brief |
| 300-312 | `_serialize_brief()` | PaperBrief → dict（手写，未走 serializer） |
| 315-327 | `PaperBriefView` GET | 返回 brief（无则 404） |
| 330-348 | `PaperBriefRegenerateView` POST | **同步阻塞** 调 `generate_brief` |
| 351-378 | `_TOKEN_RE` / `_tokens()` / `_caption_coverage()` / `_FIGURE_MATCH_THRESHOLD` | 渲染辅助（**应在 render 层！**） |
| 381-393 | `_emit_figure_md()` | markdown 拼接 |
| 396-453 | `PaperMarkdownView` GET | sections + figures interleave + claims → markdown |
| 456-466 | `FigureView` GET | figure PNG file response |
| 469-476 | `ClaimsView` GET | claims list（仅复用 ClaimSerializer） |
| 481-485 | `_do_extract()` | trigger worker，惰性 import |
| 488-493 | `_do_interpret()` | 同上 |
| 496-512 | `_do_render()` | 同上 |
| 515-525 | `ExtractTriggerView` POST | enqueue extract job |
| 528-538 | `InterpretTriggerView` POST | enqueue interpret job |
| 541-556 | `RenderTriggerView` POST | enqueue render job（验 fmt） |
| 559-564 | `JobStatusView` GET | `jobs.get_job` |
| 572-610 | `PaperStatusView` POST | status transition（含 `is_legal_transition`） |
| 613-619 | `_serialize_comment()` | 手写 dict |
| 622-652 | `PaperCommentListView` GET/POST | 列表 + append-only |
| 655-687 | `PaperCommentDetailView` PATCH | 仅允许 `hidden` 改 |
| 690-723 | `PaperTagListView` GET/POST | 加 tag（IntegrityError → duplicate） |
| 726-734 | `PaperTagDetailView` DELETE | |
| 737-756 | `_serialize_backlink_out/in()` | 手写双向 |
| 759-818 | `PaperBacklinkView` GET/POST | 双向 + dst 解析 |
| 821-842 | `PaperPdfView` GET/HEAD | ft-029 PDF 服务 |
| 845-859 | `PaperBacklinkDetailView` DELETE | |

**功能簇分布**（行权重）：
- papers read（list/detail/markdown/figure/claims）：230 行 ≈ 27%
- triggers（extract/interpret/render/job）：87 行 ≈ 10%
- user_* layer（status/comment/tag/backlink）：250 行 ≈ 29%
- brief（GET/regenerate）：42 行 ≈ 5%
- PDF：30 行 ≈ 3.5%
- 渲染辅助（`_caption_coverage` + `_emit_figure_md` + `PaperMarkdownView`）：100 行 ≈ 12%（**错位**）
- helpers + resolve + health：~90 行 ≈ 10%

## 3. 耦合 hotspot

每条带：严重度 (1=阻塞 / 2=重要 / 3=次要) · 难度 · 阻塞 ft-034 · 阻塞 ft-030。

| # | hotspot | 文件:行 | 严重 | 难度 | ft-034 | ft-030 |
|---|---|---|---|---|---|---|
| H1 | **`views.py` 单文件 859 行**，5 个职能簇混合（papers / user_* / trigger / brief / pdf / markdown） | `apps/api/views.py:1-859` | 1 | 1d | yes | yes |
| H2 | **`PaperBriefRegenerateView.post()` 同步阻塞调 LLM**（response 等数十秒），与 ft-028 trigger pattern (`enqueue → 202`) 不一致 | `views.py:333-348` | 1 | 2h | no | yes（ft-030 search 必须保异步预算） |
| H3 | **`PaperListView.get()` 110 行 + 6 个 N count 查询**（section/figure/table/claim/comment + tags + statuses + briefs）；当 `q` 走 icontains，是 ft-030 FTS5 切换的主战场 | `views.py:102-203` | 1 | 1d | yes | **yes（必须先解耦再加 FTS）** |
| H4 | **DTO 手写散点**：`_serialize_brief / _serialize_comment / _serialize_backlink_in / _serialize_backlink_out` 四处手写 dict，未走 `serializers.py`（Comment/Backlink 有 Serializer 但仅 wrap 已组装的 dict，等于"双层胶水"） | `views.py:300-312, 613-619, 737-756`；`serializers.py:109-138` | 2 | 4h | yes | no |
| H5 | **`_caption_coverage` / `_emit_figure_md` / `PaperMarkdownView` 100 行算法逻辑写在 views.py**——这是 render/markdown 层职责，不该在 API 层 | `views.py:351-453` | 2 | 4h | no | no |
| H6 | **`ingest_views.py:_save_pdf` 副作用写 `Paper`**（行 51-58），ingest view 直接写 ORM，不走 service。Paper 创建语义与 `apps/extract/signals._ensure_paper_fk` 重复（注释自承） | `ingest_views.py:38-58` | 2 | 3h | yes | no |
| H7 | **trigger 三胞胎重复**（Extract/Interpret/RenderTriggerView）：每个 view 自己 enqueue + status 200，但 `_do_extract/_do_interpret/_do_render` 在 views.py 与 ingest.py:_run_extract/_run_interpret/_run_render **逐字重复** | `views.py:481-512` vs `ingest.py:22-57` | 2 | 2h | no | no |
| H8 | **`PaperDetailView.get()` 90 行 + 双路径（Paper 行存在 / 不存在）+ 6 个 ORM 查询**，分支条件复杂；legacy "no extract data" 404 contract 与 ft-028 paper_key 路径耦合 | `views.py:217-297` | 2 | 6h | yes | no |
| H9 | **认证缺失 + 全局 0 个 `permission_classes`**：所有 view 默认走 DRF 全局（settings 未公开 require_auth）；桌面端单用户 OK，但 v1.x 公开分发要补——ft-034 是用户选择前端栈的 sprint，认证立项需要先把 view 拆好 | 所有 view | 3 | 项目级 | yes（间接） | no |
| H10 | **`resolve_paper()` Http404 副作用混淆**：`PaperBacklinkView.post()` 用 try/except Http404 来"解析 dst"（views.py:788-794）—— Http404 不是常规控制流；应写 `Paper.objects.filter(...).first()` + 自定义 404 | `views.py:788-794` | 3 | 1h | no | no |
| H11 | **filter 校验散点**：`_VALID_STATUS_FILTERS` 在 views.py 顶部、`is_legal_transition` 在 papers/models、`fmt in {excalidraw,svg}` 硬编码在 RenderTriggerView——校验规则三处分散 | `views.py:90, 544-548, 587, 596` | 3 | 2h | no | no |
| H12 | **`ingest_views.py:115` import `sources.pdf_fetcher._download`**——直接 import 模块下划线私有函数（"绕过 Item 包装"），跨 app 边界访问内部 API | `ingest_views.py:115` | 3 | 2h | no | no |
| H13 | **`subscriptions_views.py:_do_run_subscription`** 在 worker 线程调 `call_command("run_subscription")` —— 子进程 capture stdout/stderr 是反模式（应直接调 service function） | `subscriptions_views.py:127-142` | 3 | 3h | no | no |
| H14 | **`jobs.py:_JOBS` 进程级 dict + threading.Lock**——sidecar 重启即丢；`JobInfo.status` 字符串无 enum，与前端 `JobStatus` ts type 漂移（见 §4）；scheduler in-process 限制了未来扩展 | `jobs.py:51-52` | 3 | 1d | no | no |
| H15 | **错误响应 schema 不一致**：多数 `{"detail": "..."}`，但 `PaperStatusView` 加了 `from / to` 二字段（views.py:599-606），`PaperTagListView` 加了 `duplicate: true`（views.py:722）——前端 axios error handler 没法统一 | `views.py:599-606, 722` | 3 | 2h | no | no |

## 4. DTO 漂移清单

后端 serializer / view dict 构造 vs 前端 `frontend/src/types/paper.ts` + `frontend/src/api/*.ts`。

### D1 `PaperListItem`（**已 ft-033 同步，但 status enum 不强制**）

后端 `serializers.py:82-104` `PaperListItemSerializer.fields` ≈ 前端 `papers.ts:20-43 PaperListItem`：

| 字段 | 后端 | 前端 | 状态 |
|---|---|---|---|
| `arxiv_id` | CharField allow_null | `string` | **mismatch**（后端可 null，前端非可选）→ frontend 已用 `normalizePaperListItem` 兜 fallback |
| `paper_key` | CharField | `string` | OK（后端总有，前端 normalize 仍兜空字符串） |
| `title` | CharField allow_blank | `string` | OK |
| `status` | CharField | `PaperStatus` (literal union) | **drift**：后端 plain string，没强 enum；前端 6 种 literal——任何拼写错都漏判 |
| `tags` | ListField[CharField] | `string[]` | OK |
| `n_comments / n_sections / n_figures / n_tables / n_claims` | IntegerField | `number` | OK |
| `tldr_zh / abstract_zh / abstract_en` | CharField | `string` | OK |
| `keywords` | ListField (default list) | `string[]` | OK |
| `has_brief` | BooleanField | `boolean` | OK |

### D2 `PaperDetail`（**未走 serializer，纯 dict**）

`views.py:256-297` 手写 dict — 没有任何 serializer 验证 schema，与 `papers.ts:150-171 PaperDetail` 隔空对：

| 字段 | 后端组装 | 前端 type | 状态 |
|---|---|---|---|
| `arxiv_id` | str | string | OK |
| `paper_key` | only when paper resolved | `string?` | OK（前端 optional） |
| `title` | only when paper resolved | `string?` | OK |
| `status` | only when paper resolved | `PaperStatus?` | OK |
| `tags` | only when paper | `string[]?` | OK |
| `n_comments` | only when paper | `number?` | OK |
| `has_pdf` | bool, both branches | `boolean?` | OK |
| `pdf_url` | str or null | `string \| null \| undefined` | OK |
| `abstract` | str（fallback ""）| `string?` | OK |
| `brief` | nested PaperBriefDTO 或 null | `PaperBriefDTO \| null` | OK |
| `sections / figures / tables / claims` | serializer many=True | DTO[] | OK |
| `equations` | **手写 dict 列表**（`views.py:261-270`）—— 没用已存在的 `EquationSerializer`！ | `EquationDTO[]` | **drift**：后端手写漏 `material_id/eq_label/bbox/paper_arxiv_id`；前端 `EquationDTO` 也漏 `paper_arxiv_id`（与 `serializers.py:38-43 EquationSerializer.fields` 不一致） |

### D3 `PaperBrief`（**手写 `_serialize_brief` 与 ts type 完全对齐，但绕过 serializer**）

`views.py:300-312 _serialize_brief()` 手写 dict，与 `papers.ts:137-148 PaperBriefDTO` 字段一一对应（`abstract_zh / keywords / method_summary_zh / key_innovation / limitations / for_you / tldr_zh / perspective_used / model_used / generated_at`）。状态：**字段 OK，但无 schema 验证**——后端 model 字段加减时前端会无感 break。

### D4 `Comment` / `Backlink`（**双层胶水**）

- `views.py:613-619 _serialize_comment()` 先把 model 拍成 dict，然后 `CommentSerializer(items, many=True).data` 再 wrap 一次（serializer 仅作 schema 文档）—— 等同 dataclass dump。冗余但无 drift。
- `views.py:737-756 _serialize_backlink_out/in()` 同样模式。前端 `paper.ts:31-47 BacklinkEdge` `src_key/dst_key` 互斥写成 optional——后端在 GET 里**两个字段都存在但只填一边**，前端 type 表达不清晰但用法正确。

### D5 `Job` （**status enum drift**）

后端 `jobs.py:31` `status: str = "queued"`，状态机 `queued | running | succeeded | failed`（4 态）。
前端 `frontend/src/api/jobs.ts:3-8` `JobStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled"`（5 态）。
**mismatch**：
- 前端有 `pending` / `cancelled`，后端没生产
- 后端有 `queued`，前端 type 没列
- 前端 type 实际 fallback 到 `string` 兜底（`JobStatus | string`），所以运行时不爆，但 type-narrow 失效

### D6 `Subscription` Serializer（**`run_subscription` 不返回 schema，只 stdout_tail**）

`SubscriptionRunView` 返回 `{job_id, status}` —— 前端没有对应 ts 类型（`frontend/src/api/subscriptions.ts` 未读，但既然不在 grep 出现，前端可能未消费 run 结果）。

### D7 `IngestResponse`（**OK**）

`ingest_views.py` 三入口都返回 `{job_id, status, paper_id, pdf_path}`，与 `frontend/src/api/ingest.ts:5-10 IngestResponse` 一致。

### D8 `BacklinkSerializer.outgoing/incoming` 顶层 wrapper

后端 `BacklinkSerializer({"outgoing": [...], "incoming": [...]})` 与前端 `BacklinkDTO` 一致。但 `addPaperBacklink` 后端返回单条 `_serialize_backlink_out(bl)`（views.py:816）—— 前端 `addPaperBacklink` 类型注解 `BacklinkEdge`，OK。

**汇总**：8 个域，2 处实际 drift（D2 equations 后端手写漏字段；D5 job status enum），2 处 schema-by-comment（D2/D3 没真 serializer），4 处 OK。

## 5. views.py 拆分提议

把 859 行的 `views.py` 切到 `apps/api/views/` package 下，按"前端调用类簇"切（不按 model 切，避免 status/tag 跨 module）：

```
apps/api/views/
├── __init__.py        # re-export 全部 view class，保 urls.py import 不动
├── _common.py         # PAPER_KEY_RE / resolve_paper / _default_pdf_path / _VALID_STATUS_FILTERS
├── health.py          # HealthView                        ~15 行
├── papers.py          # PaperListView / PaperDetailView    ~200 行
├── markdown.py        # PaperMarkdownView + caption helpers（或迁到 apps/render/markdown.py） ~110 行
├── figures.py         # FigureView / ClaimsView            ~25 行
├── triggers.py        # Extract/Interpret/RenderTriggerView + JobStatusView + _do_* helpers
│                       （或彻底迁到 ingest.py 单一来源）   ~95 行
├── user_layer.py      # PaperStatus / PaperComment* / PaperTag* / PaperBacklink*  ~250 行
├── brief.py           # PaperBriefView / PaperBriefRegenerateView  ~50 行
└── pdf.py             # PaperPdfView                       ~30 行
```

**实施门槛**：
1. 第一步 `__init__.py` re-export——`urls.py` 不动，零回归。
2. 第二步把 `_serialize_*` 手写 dict 收编到 `serializers.py`，view 只调 serializer。
3. 第三步合并 trigger 重复（views.py 的 `_do_extract` 与 ingest.py 的 `_run_extract` 选一个 source of truth；建议保 ingest.py，views/triggers.py 直接 import 用）。
4. 第四步 `markdown.py` 整体下沉到 `apps/render/markdown.py`，view 只剩 thin proxy（caption_coverage 是确定性算法，按 CLAUDE.md "工具 vs LLM 边界"应是 render 层工具）。

**预期收益**：
- 单文件 < 250 行，读懂时间 -60%
- ft-030 FTS5 切换只动 `papers.py` + 一个新 `search.py`，contained blast radius
- ft-034 前端栈切换不需要后端连改

## 6. 解耦改造提议

按收益 / 难度排序，最多 10 条：

| # | 改造 | 解决 hotspot | 难度 | 优先级 |
|---|---|---|---|---|
| R1 | **`views.py` package 拆分**（见 §5），分 8 个 sub-module，re-export 兼容旧 import | H1 | 1d | **P0**（ft-030 前置） |
| R2 | **`PaperBriefRegenerateView` 异步化**：改成 `enqueue(generate_brief, ...)` → 202 + job_id；前端轮询 `/api/jobs/<id>/`。和 ft-030 search 一起把"长操作"标准化为 trigger pattern | H2 | 2h | **P0** |
| R3 | **抽 `apps/api/services/papers.py`**：把 `PaperListView` 里 6 个 count agg + tag/status/brief join 拎成 `list_papers(filters) -> list[dict]`；view 只剩 query-param 解析 + serializer。ft-030 加 FTS5 时只需在此 service 内换 backend（icontains → fts5_match） | H3 | 1d | **P0**（ft-030 阻塞解除） |
| R4 | **DTO 收编到 `serializers.py`**：补 `PaperDetailSerializer / PaperBriefSerializer / CommentSerializer.from_model() / BacklinkEdgeSerializer`，删除 4 个 `_serialize_*` helper；`PaperDetailView` 用 `PaperDetailSerializer(paper, context={...}).data` 一行 | H4, D2, D3, D4 | 6h | **P1** |
| R5 | **`PaperMarkdownView` 下沉**：把 `_caption_coverage / _emit_figure_md / PaperMarkdownView.get` 迁到 `apps/render/markdown.py`，views.py 留 30 行 thin view | H5 | 4h | P1 |
| R6 | **`ingest_views._save_pdf` 抽 service**：`apps/papers/services.py: ensure_paper_with_pdf(arxiv_id, pdf_bytes)`；ingest view 调 service，统一 `_ensure_paper_fk` 语义不再两处分散 | H6 | 3h | P1 |
| R7 | **trigger 函数 single-source**：删 `views.py:481-512` 的三个 `_do_*`，改 import `apps.api.ingest._run_extract/_run_interpret/_run_render`；ingest.py 是 chain 真源头 | H7 | 1h | P1 |
| R8 | **统一错误响应 schema**：`apps/api/errors.py` 出 `def error(detail, code=None, **extra)` 工具，强制 `{"detail": str, "code"?: str, **extra}` 格式；前端加 `axios interceptor` 接住 | H15 | 4h | P2 |
| R9 | **fix DTO drift D5（job status）**：后端引 `jobs.py: JobStatus` enum（`queued/running/succeeded/failed`），前端 `frontend/src/api/jobs.ts: JobStatus` 同步去掉不存在的 `pending/cancelled` | D5 | 30min | P2 |
| R10 | **fix DTO drift D2（equations）**：`PaperDetailView` 用 `EquationSerializer(equations_qs, many=True).data`，前端 `EquationDTO` 补 `paper_arxiv_id / eq_label / bbox` | D2 | 30min | P2 |

**ft-030 v1.3 / FTS5 facet endpoint 上线先决条件**：R1 + R3 必须先做，否则新 `/api/search/` 和 `PaperListView` 的 `?q=` 共存会形成"两套 search backend"——这是经典的迁移陷阱。

**ft-034 前端栈切换先决条件**：R1 + R4 + R8。前端栈切（无论 Tauri/Electron/SolidJS）会重新走一遍 axios client 接线，DTO + error schema 不统一会被放大。

## 7. 不在范围 / 移交其它 group

| 议题 | 文件 | 移交 group |
|---|---|---|
| `generate_brief` 同步 LLM 调用本身（R2 只改"何时调"，怎么调归 brief 生成器） | `apps/papers/brief_generator.py` | A（services） |
| `resolve_pdf_path` 解析顺序 + legacy 路径策略 | `apps/papers/paths.py` | A |
| extract / interpret / render service contract（trigger view 只是 thin enqueue） | `apps/extract/*`, `apps/interpret/*`, `apps/render/*` | A |
| APScheduler in-process queue 是否升级到 Celery / RQ | `apps/api/jobs.py:51-122` + `apps/core/scheduler.py` | A（scheduler）+ ops |
| `subscriptions.loader` YAML round-trip 与 ruamel | `subscriptions/loader.py` | A |
| `sources.pdf_fetcher._download` 私有函数 import（H12 暴露 API 边界破坏） | `sources/pdf_fetcher.py` | A（sources） |
| 认证策略选型（H9）—— 桌面端单用户 vs 公开分发 | `explore_os/settings.py` | C（infra） |
| frontend axios client + error interceptor（R8 后端定 schema，前端实现归 frontend） | `frontend/src/api/client.ts` | D（frontend）|
| migration 不要 raw PG SQL（CLAUDE.md 长期形态约束）—— views/serializers 已合规，但 service 层提议时要复查 | apps/*/migrations/ | A |

**review-B 范围内未触碰但相关**：`apps/api/tests_*.py` 5 个 test 文件作为契约 reference 读取，未发现需要更新的契约硬码（待 R1-R10 实施时同步改）。

