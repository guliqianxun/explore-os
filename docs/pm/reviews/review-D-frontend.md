---
review_id: review-D-frontend
review_group: D
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---

# Review D — Frontend api / types / hooks

## 1. 范围确认

审过的文件（35 个）：

- `frontend/src/api/`：client.ts (48), papers.ts (352), claims.ts (9), ingest.ts (44), jobs.ts (66), subscriptions.ts (90)
- `frontend/src/types/`：仅 `paper.ts` (69)
- `frontend/src/hooks/`：仅 `useJobPolling.ts` (47)
- `frontend/src/lib/`：fonts.ts (27), statusMachine.ts (84), utils.ts (6)
- `frontend/src/stores/`：仅 `jobsStore.ts` (23)
- 6 个 page：PaperListPage (414), PaperDetailPage (135), ReadingStation (288), SpeedReadView (273), IngestPage (213), SubscriptionPage (201)
- 关键 component：BriefSection (199), VerdictActions (193), PaperCard (146), HeroPaperCard (154), ClaimCard (143), SkimCard (65), ActiveRunsBanner (84), IngestProgressItem (131), reading/* (10 个文件 1700+ 行) — NotesPane/CommentList/CommentForm/TagEditor/BacklinkEditor/EvidenceItem/SpeedCardPane/ClaimCard/StatusPill/ActionBar
- 对照参考（只读）：`apps/api/serializers.py` (185), `apps/api/views.py` (859), `apps/papers/models.py` (lines 30-87 状态机)
- 配置：`frontend/src/main.tsx` (QueryClient defaults), `frontend/src/App.tsx` (路由)
- 构建产物：`frontend/dist/assets/index-D-EL4EwY.js` 636 KB（单 chunk，无 manual splits）

未审：UI primitives (`components/ui/`)、`PdfViewer`、`SubscriptionEditor`、`SubscriptionCard`、`ChipInput`、样式文件。

## 2. api 模块结构图

api/* 都是「裸函数 + 手写 fetch」，没有任何「自家 hook 封装」（`useXxx`）；所有 `useQuery/useMutation` 都散在 page/component 里。

| 模块 | 导出 | inline 使用点 |
|---|---|---|
| `api/client.ts` | `getApi()` 单例（基于 Electron preload `window.explore.getBackendPort()`，浏览器 fallback 8000） | 被所有其它 api/*.ts import；page/component 直接 import 4 处用于拼图片 URL：`PaperListPage:118-126`、`SpeedReadView:83-91`、`SpeedCardPane:145-153`、`EvidenceItem:138-146`，外加 `CommentList:30` 直接调 `api.patch('/comments/{id}/')` |
| `api/papers.ts` | 17 个函数：`listPapers`、`getPaperDetail`、`getPaperClaims`、`figureUrl`、`setPaperStatus`、`listPaperComments`、`appendPaperComment`、`listPaperTags`、`addPaperTag`、`removePaperTag`、`listPaperBacklinks`、`addPaperBacklink`、`removePaperBacklink`、`headPaperPdf`、`pdfFileUrl`、`searchPapersTypeahead`、`regeneratePaperBrief` + 9 个 DTO interface | PaperListPage、PaperDetailPage、ReadingStation、SpeedReadView、SpeedCardPane、BriefSection、VerdictActions、ActionBar、StatusPill、CommentForm、CommentList、TagEditor、BacklinkEditor、NotesPane、EvidenceItem、HeroPaperCard、PaperCard、SkimCard、ClaimCard（×2）|
| `api/claims.ts` | **空壳** — 仅 `export type` re-export 三个 DTO | 0 个 component import（注释说占位 ft-032） |
| `api/ingest.ts` | `ingestUpload/ingestArxiv/ingestUrl` + `IngestResponse` | IngestPage |
| `api/jobs.ts` | `triggerExtract/triggerInterpret/triggerRender/getJob` + `JobStatus`/`JobInfo`/`TriggerResponse` | useJobPolling、IngestPage（直接调 `getJob` 跑独立 setInterval） |
| `api/subscriptions.ts` | `listSubscriptions/getSubscription/createSubscription/updateSubscription/deleteSubscription/runSubscription` + DTO 7 个 | SubscriptionPage（其它页都不用） |

观察：

1. **没有自家 hook**：`useTanStackQuery({ queryKey, queryFn: listPapers })` 这种胶水代码在 19 处重复发明；`api/` 模块本身没有 `usePapers()` / `usePaperDetail()` 之类对应抽象。
2. **claims.ts 名存实亡**：唯一的 9 行只是 re-export，又给 ft-032 留坑。当前 claim DTO 实际从 `@/api/papers` 直接 import（见 SpeedReadView:6-12, EvidenceItem:4-12, ClaimCard:3, ReadingClaimCard:3）；`@/api/claims` 0 引用。
3. **client.ts baseURL 解析变异为 useQuery**：4 处 component 用 `useQuery({queryKey:["api-base"], queryFn: () => (await getApi()).defaults.baseURL })`。这本应是 sync helper，被错塞进 query 缓存仅为了「拿到字符串后能 derive img src」；这条件就值得抽 `useApiBase()` 或干脆 prop drill。
4. **错误处理不一致**：`subscriptions.listSubscriptions` 自吞 throw 返回 `[]`（line 38）；其它 14 个 list 函数 throw 抛上去。前端 page 偶尔 alert（IngestPage:51,60,69），偶尔显示 `(error as Error).message`（PaperListPage:213, PaperDetailPage:85），偶尔静默吞掉。


## 3. 耦合 hotspot

> 严重度：3=阻塞 / 2=应修 / 1=改进项。"阻塞 ft-030" 指能否影响 iter-019 ft-030 落地。

**H1 — `papers.ts` 17 函数 / 352 行的全能模块**
文件：`frontend/src/api/papers.ts`
单文件塞 list/detail/claim/comment/tag/backlink/pdf/typeahead/regenerate 九条业务线 + 9 个 DTO interface。任何 paper 子能力变更都得动这一个文件，git blame 已经热到完全失去信号。**严重度 3 / 阻塞 ft-030：是**（ft-030 涉及深度解读字段调整，会再次撞 papers.ts）。

**H2 — `useQuery({queryKey:["api-base"], queryFn})` 把 baseURL 错塞 query 缓存**
文件：`PaperListPage:118-126`、`SpeedReadView:83-91`、`SpeedCardPane:145-153`、`EvidenceItem:138-146`
`getApi()` 是 sync helper（preload 暴露的 port 已 cache），4 处都为「拿到 baseURL 后拼图片 URL」把它包成 react-query。结果：图片渲染依赖 query loading state，离线/重渲时闪烁；缓存 key `["api-base"]` 没有失效策略，与 Electron port discovery 语义错位。**严重度 2 / 阻塞 ft-030：否**。

**H3 — claims.ts 9 行空壳，0 引用**
文件：`frontend/src/api/claims.ts`
仅 re-export `Claim/Evidence/ClaimList` 三个 type，注释占位 ft-032。实际 claim DTO 都从 `@/api/papers` import（`SpeedReadView:6-12`、`EvidenceItem:4-12`、`ClaimCard:3`、`ReadingClaimCard:3`）。死代码 + 反向耦合（claim 反过来贴在 papers 模块上）。**严重度 1 / 阻塞 ft-030：否**。

**H4 — `subscriptions.listSubscriptions` 自吞 throw 返回 `[]`**
文件：`frontend/src/api/subscriptions.ts:38`
唯一一个把网络错误吞成 `[]` 的 list 函数，UI 区分不出"真的没订阅"vs"后端 500"。其余 14 个 list 都 throw。错误处理风格在前端 page 内还分三派：alert（IngestPage:51,60,69）/ 显式 message 渲染（PaperListPage:213, PaperDetailPage:85）/ 静默。**严重度 2 / 阻塞 ft-030：否**。

**H5 — 双轨 polling：`useJobPolling.ts` vs IngestPage `setInterval`**
文件：`frontend/src/hooks/useJobPolling.ts` + `frontend/src/pages/IngestPage.tsx`
hook 已封装 react-query polling，但 IngestPage 仍直接 `setInterval(getJob, …)` 跑独立轮询。两条线对同一 job 的 status 可能不一致，且 unmount 清理路径分叉。**严重度 2 / 阻塞 ft-030：是**（ft-030 deep-interpret 进度条会沿用 job polling）。

**H6 — `jobsStore.ts` 23 行 Zustand 与 react-query 缓存职责重叠**
文件：`frontend/src/stores/jobsStore.ts`
Zustand 仅存 `activeRuns` 列表，但 `getJob` 又走 react-query，两边都有 job 状态镜像。ActiveRunsBanner 读 zustand，IngestPage / useJobPolling 读 query cache。`useEffect` 同步 → 推 zustand 是 footgun。**严重度 2 / 阻塞 ft-030：否**。

**H7 — Vite 主 chunk 636 KB 单一 bundle**
文件：`frontend/dist/assets/index-D-EL4EwY.js` + `vite.config.ts`（无 `manualChunks`）
Excalidraw / pdf 渲染 / shadcn 全打进同一 chunk。Electron 冷启首屏被拖累；ft-030 引入更重的 brief renderer 后会更糟。**严重度 2 / 阻塞 ft-030：否**（但马上会变成 1→2）。

**H8 — paper card 三件套近似复制**
文件：`PaperCard (146)` / `HeroPaperCard (154)` / `SkimCard (65)`
三个组件渲染同一 PaperListItem DTO，差异仅在 layout 与图片尺寸；prop 表 80% 重叠。新增字段（如 ft-030 deep_interpret 标记）需三改。**严重度 1 / 阻塞 ft-030：是**（轻度，会让 ft-030 改三处）。

**H9 — `CommentList:30` 绕过 api/* 直接 `api.patch('/comments/{id}/')`**
文件：`frontend/src/components/reading/CommentList.tsx:30`
跳过 `api/papers.ts` 的封装边界，直接拿 axios 实例打 PATCH。下次后端改 comment endpoint，grep `papers.ts` 找不到这处。**严重度 2 / 阻塞 ft-030：否**。

**H10 — reading/* 10 个文件 1700+ 行无统一 store**
文件：`frontend/src/components/reading/*`
NotesPane / CommentList / CommentForm / TagEditor / BacklinkEditor / EvidenceItem / SpeedCardPane / ClaimCard / StatusPill / ActionBar 都通过 `paperId` prop 各自 useQuery，缺一层 ReadingStation level 的 context / store；prop drilling + 重复 fetch。**严重度 2 / 阻塞 ft-030：否**。

**H11 — `setPaperStatus` 散用，状态机校验只在 `lib/statusMachine.ts` 做**
文件：`frontend/src/lib/statusMachine.ts (84)` + `VerdictActions:` + `StatusPill:` + `ActionBar:`
前端有 84 行 statusMachine 镜像后端 `apps/papers/models.py:30-87`。两边任何一处加 status 都要双改，且没有 codegen 绑定。**严重度 2 / 阻塞 ft-030：否**。

**H12 — DTO interface 直接散落在 `papers.ts` 而非 `types/`**
文件：`frontend/src/api/papers.ts` 9 个 interface vs `frontend/src/types/paper.ts` 仅 69 行
types/ 目录形同虚设；component import DTO 的路径混乱（有从 `@/api/papers`，也有从 `@/types/paper`）。**严重度 1 / 阻塞 ft-030：否**。

## 4. DTO 漂移清单

> 与 `apps/api/serializers.py` 字段集对照。「严重度」3=runtime 字段缺失/error，2=类型不一致但 fallback 能跑，1=注释/文档漂移。

**D1 — `EquationDTO` 漏 3 字段**
前端 `papers.ts:105-111` 5 字段：`material_id/seq/page/latex_or_text/inline_or_display`
后端 `EquationSerializer:37-43` 8 字段：多 `paper_arxiv_id` / `eq_label` / `bbox`
`bbox` 是用于点击定位的载荷，前端要做 ft-030 的"公式跳原文"会立刻撞墙。**严重度 2 / 阻塞 ft-030：是**（公式 anchor 用得上 bbox）。

**D2 — `JobStatus` enum 5 vs 4 漂移**
前端 `jobs.ts:3-8`：`pending | running | succeeded | failed | cancelled`
后端 `apps/api/jobs.py:31`：`queued | running | succeeded | failed`
`pending` 在后端不存在（实际是 `queued`），`cancelled` 后端从未发出。useJobPolling / IngestPage 比对 `pending/cancelled` 的所有分支都死代码或永远 false。**严重度 2 / 阻塞 ft-030：是**（ft-030 deep-interpret job 进度态切换会被 enum 误差挡）。

**D3 — `PaperListItem` 字段顺序与「partial-during-rollout」语义错位**
前端 `papers.ts:20-43` 把 16 字段全声明 required；wire 层用 `PaperListItemWire = Partial<...> & Pick<...>`（line 46-50）做兜底。但后端 serializer line 87-104 确实把 `arxiv_id` 标 `required=False`，意味着 wire 层跟 DTO 真实可空性反了：DTO 写 required，normalize 又强吃 default。下游消费者拿到的 `paper_key=""` 会被当成有效 key 写进 router 路径。**严重度 2 / 阻塞 ft-030：否**。

**D4 — `PaperBriefDTO.generated_at` 类型 `string | null`，serializer 未定义此字段**
前端 `papers.ts:137-148` 包括 `generated_at`，但 `serializers.py` 通篇没有 `BriefSerializer` 类（grep 仅 `class \w+Serializer` 见 18 处，无 Brief）。Brief 由 `papers/models.py` 的 PaperBrief 模型直出还是手工 dict 拼？前端类型在猜。**严重度 2 / 阻塞 ft-030：是**（ft-030 接 deep_interpret_rich，需要稳定 brief schema）。

**D5 — `ClaimEvidence` 在 `types/paper.ts` 与 `ClaimEvidenceDTO` 在 `api/papers.ts` 双定义**
`types/paper.ts:58-62`（ft-029 引入）vs `api/papers.ts:113-116`（papers.ts 私有），两份等价 type 命名不同。前端 component import 路径混乱（一份从 types，另一份从 papers）。后端只一份。**严重度 1 / 阻塞 ft-030：否**。

**D6 — `CounterSignal` 同上双定义**
`types/paper.ts:64-69` vs `api/papers.ts:118-123`。**严重度 1 / 阻塞 ft-030：否**。

**D7 — `PaperDetail.has_pdf / pdf_url` 标 optional，但后端 rpt-013 起一直返回**
`papers.ts:159-161` 注释"present from backend rpt-013"却仍 `?:`，导致每个 PdfViewer 用点都要 `paper.has_pdf ?? false`。要么后端把字段 lock required，要么前端 wire normalize 时填 default — 现在两边都没做。**严重度 1 / 阻塞 ft-030：否**。

## 5. types/paper.ts 拆分提议

`types/paper.ts` 当前只 69 行，承担「ft-028 锁定的 stable DTO 总线」角色，但实际上 `api/papers.ts` 又私自塞了 9 个 interface（PaperListItem、SectionDTO、FigureDTO、TableDTO、EquationDTO、ClaimEvidenceDTO、CounterSignalDTO、ClaimDTO、PaperBriefDTO、PaperDetail），且 ClaimEvidence/CounterSignal 在 types/ 里也有重名版本（见 §4 D5/D6）。建议：

1. **`types/paper.ts` 升级为 single source of truth**：把 `papers.ts` 9 个 interface 全部迁过来，按子域拆三个文件 — `types/paper-core.ts`（PaperListItem / PaperDetail / PaperStatus / StatusFilter）、`types/paper-material.ts`（Section/Figure/Table/Equation/Citation DTO，对应后端 extract_*）、`types/paper-claim.ts`（Claim/ClaimEvidence/CounterSignal/PaperBrief，对应 interpret_*）。命名与后端三段中台对齐（CLAUDE.md「拆三段中台」）。
2. **`api/papers.ts` 只 re-export 不重定义**：保留 `import type` + `export type`，禁止再写 `export interface`。codegen 化第一步。
3. **`papers.ts` 同时移出 `normalizePaperListItem`**：归到 `types/paper-core.ts` 旁的 `normalize.ts`，让 wire ↔ DTO 转换跟 fetch 解耦。
4. ft-030 落 deep_interpret_rich 时直接在 `types/paper-claim.ts` 加字段，不再触碰 papers.ts。这条改造能直接退烧 H1 / H12 / D5 / D6。

## 6. 解耦改造提议

> 按「先治痛 → 再治痒 → 长期」三档，每条标 ROI（H/M/L）和与 ft-030 的关系。

**R1（先治痛）— 拆 `papers.ts`，先按业务线劈四个模块**
新增 `api/paper-list.ts` / `api/paper-detail.ts` / `api/paper-claim.ts` / `api/paper-user.ts`（comment/tag/backlink/status）。`papers.ts` 留 facade barrel 导出。配合 §5 的 types/* 拆分。**ROI: H / ft-030 帮助：高**（papers.ts 不再阻塞）。

**R2（先治痛）— 引入「自家 hook 层」 `hooks/api/`**
为 19 处 inline `useQuery` 抽对应 `usePapers` / `usePaperDetail` / `usePaperClaims` / `usePaperBrief` / `useApiBase`。所有 component 改为消费 hook，不再直接 `useQuery({queryKey, queryFn: listPapers})`。把 query key 命名集中在 `hooks/api/keys.ts`，便于精确 invalidate。**ROI: H / ft-030 帮助：高**。

**R3（先治痛）— 修齐 JobStatus / EquationDTO / Brief schema 三处漂移**
后端将 `apps/api/jobs.py:31` enum 暴露成常量，前端 `JobStatus` 直接 type-import；`EquationDTO` 补 `paper_arxiv_id/eq_label/bbox` 三字段；`PaperBriefDTO` 在 serializers.py 落显式 `BriefSerializer`。**ROI: H / ft-030 帮助：是**（D2 + D4 是 ft-030 直接阻塞项）。

**R4（治痒）— 收拢 polling 单一入口**
删除 IngestPage 的独立 `setInterval`，全走 `useJobPolling`；`jobsStore.ts` 23 行 zustand 改为「仅缓存 visible-banner UI 选择」，job 真值仍走 query cache。同时把 ActiveRunsBanner 改为读 `useActiveJobs()` hook。**ROI: M / ft-030 帮助：中**（H5 / H6 一并处理）。

**R5（治痒）— 删 `claims.ts`，把 ft-032 占位文档化**
9 行空壳 0 引用直接删；ft-032 真要做的时候在新 PR 落 `api/paper-claim.ts`（R1 已铺路）。`@/api/claims` import 全局 grep 0 处可放心 drop。**ROI: M / ft-030 帮助：低**。

**R6（治痒）— 状态机 codegen，消灭前后端两份 status 表**
后端 `apps/papers/models.py:42 STATUS_TRANSITIONS` 在 build 阶段导出 JSON，前端 `lib/statusMachine.ts` 编译期消费。两份 84 行手抄镜像消失。**ROI: M / ft-030 帮助：否**。

**R7（治痒）— Vite `manualChunks` 拆 vendor / excalidraw / pdf**
`vite.config.ts` 加 `build.rollupOptions.output.manualChunks`，把 excalidraw、@react-pdf-viewer、@radix-ui 各劈一个 chunk；首屏 JS 目标 < 250 KB。**ROI: M / ft-030 帮助：低**（但 Electron 冷启提速）。

**R8（治痒）— 三件套 PaperCard 抽公共骨架**
`PaperCard / HeroPaperCard / SkimCard` 抽 `BasePaperCard` + variant prop（hero/list/skim），剩余仅 layout 包装。新增字段一改三跟一改一。**ROI: M / ft-030 帮助：是**（H8 阻塞项）。

**R9（长期）— reading/* 引入 ReadingContext + 单 useReadingPaper hook**
ReadingStation 顶层 fetch 一次 PaperDetail，下挂 context 给 NotesPane / CommentList / TagEditor / BacklinkEditor / EvidenceItem；消除 10 个组件各自 `useQuery(["paper", id])` 的重复请求和 prop drill。**ROI: M / ft-030 帮助：低**。

**R10（长期）— 错误处理统一 `useApiError` + ToastProvider**
3 派错误处理（alert / inline / 静默）合并；`subscriptions.listSubscriptions` 自吞 throw 撤销，统一交 hook 层兜底。**ROI: L / ft-030 帮助：否**。

## 7. 不在范围 / 移交其它 group

本 review 只看了 `frontend/src/api`、`types`、`hooks`、`stores`、`lib`、6 个 page 与重 component；以下未审或需其它 review 接力：

- **UI primitives** `frontend/src/components/ui/*`（shadcn 生成层）— 未审；如有 Radix 升级或 a11y 议题留给单独 UI review。
- **PdfViewer / SubscriptionEditor / SubscriptionCard / ChipInput** — 未审；建议在 ft-029/ft-030 完成后随 review-E 收一次。
- **样式与设计系统**（tailwind.config / 全局 CSS / 主题 token）— 不在 group D 范围。
- **后端 serializers / views 修复**（D1/D2/D4 三个漂移项）— 移交 review-B 后端组（B 组已捕获 D2/D5 同一根因，建议 D 组提的字段补全合并到 B 组的 PR 序列）。
- **`apps/papers/models.py` STATUS_TRANSITIONS 导出 JSON 给前端 codegen**（R6）— 跨前后端，需 review-B 与 review-D 共商；建议落 ft-034 单独 feature。
- **BriefRegenerate 同步阻塞 LLM**（B 组 H2）— 后端议题，前端只负责落 R4 polling 收拢后正确显示进度。
- **构建优化 R7**（manualChunks）— 与 Electron sidecar 打包流水线相关，移交 review-C devops 组并行跟进。
- **Excalidraw 相关 component（v0.8 ft-021）** — 本次未触达（不在 35 文件集合内），如需独立 review 走 review-G。
