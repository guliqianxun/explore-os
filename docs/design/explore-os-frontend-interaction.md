---
title: explore-os 前端交互层设计 — 人在环路 + 阅读器
feature: ft-041
created_at: 2026-05-04
---

# explore-os 前端交互层设计

## 1. 阅读器决策：浏览器原生 PDF

### 为什么不用 pdf.js

现存 `PdfViewer.tsx` 用 pdf.js 全量渲染，存在三个问题：
1. **不可迁移** — 用户无法"把这个 PDF 另存为"或"在外部阅读器打开"并保留标注
2. **非标体验** — 选中文字、搜索、缩放都是自定义实现，与用户已有的 PDF 阅读习惯冲突
3. **维护负担** — pdf.js worker、bbox overlay、scroll sync 都是自建轮子

### 方案：浏览器原生 `<embed>` + 侧栏覆盖

```
┌──────────────────────────────────────────────────────────┐
│                    浏览器标签页                             │
│  ┌──────────────────────────┬───────────────────────────┐ │
│  │                          │                           │ │
│  │   <embed src="/api/      │   侧栏 (320px)            │ │
│  │    papers/<id>/pdf/"     │                           │ │
│  │    width="100%"          │   ┌─ Claims ──────────┐   │ │
│  │    height="100%"         │   │ Claim 1 [▸]        │   │ │
│  │                          │   │ Claim 2 [▸]        │   │ │
│  │   浏览器原生 PDF 查看器    │   │ Claim 3 [▸]        │   │ │
│  │   · 自带搜索 (Ctrl+F)    │   └───────────────────┘   │ │
│  │   · 自带缩放             │                           │ │
│  │   · 自带文字选择          │   ┌─ Evidence ────────┐   │ │
│  │   · 自带打印/下载         │   │ Fig 1  [view]     │   │ │
│  │   · 标准右键菜单          │   │ Fig 3  [view]     │   │ │
│  │                          │   │ Tab 1  [view]     │   │ │
│  │                          │   └───────────────────┘   │ │
│  │                          │                           │ │
│  │                          │   ┌─ Actions ────────┐   │ │
│  │                          │   │ [Mark Read]       │   │ │
│  │                          │   │ [Mark Kept]       │   │ │
│  │                          │   │ [Link to...]      │   │ │
│  │                          │   │ [Add to Thread]   │   │ │
│  │                          │   └───────────────────┘   │ │
│  │                          │                           │ │
│  └──────────────────────────┴───────────────────────────┘ │
│                                                             │
│  [← Back to feed]  [Status: reading ▾]  [Tags: ...]       │
└──────────────────────────────────────────────────────────┘
```

**优势**：
- PDF 是标准 HTTP 资源 (`GET /api/papers/<id>/pdf/`) — 可下载、可外部打开
- 浏览器自带的可访问性、打印、翻译
- 侧栏只做"信息增强"——不碰 PDF 渲染
- 页面跳转用 `<embed>.postMessage` 或简单 reload with `#page=N`

**降级**：无 PDF 时退回到现有 `SpeedReadView`（单列速读模式，已有）。

---

## 2. 五个交互点的前端实现

### 交互点 1: READ(p) — unseen → exposed

**触发时机**：用户打开 PaperDetailPage。

**现有基座**：`ReadingStation` 已经 auto-bump status `new→reading`。

**新增**：`PaperDetailPage` mount 时额外调 `POST /api/state/events/` 批量标记所有 claims 为 exposed。但这不是每个 claim 独立调——是**后端 signal 自动做**的（`UserPaperStatus.post_save`）。

**前端改动**：不需要额外代码。`ActionBar` 的 status 切换已经触发 signal。

**验证**：状态切到 reading 后 `GET /api/state/viewpoint/<id>/` 返回 `"state": "exposed"`。

---

### 交互点 2: VIEW_EVIDENCE(v) — exposed → confirmed

**触发时机**：用户在侧栏展开 claim card 看到 evidence 详情。

**实现**：`ReadingClaimCard` 的 `▸/▾` expand toggle 时：

```typescript
// 在 expand handler 中
if (claim.state !== "confirmed") {
  await postEvent({
    viewpoint_id: claim.claim_id,
    trigger: "VIEW_EVIDENCE",
    payload: { source: "claim_expand" },
  });
}
```

**前端改动**：
- `ReadingClaimCard.tsx`: `onExpand` 回调加 API 调用
- `ClaimCard.tsx` (drawer variant): 同理，mount 时调（drawer 里 evidence 是始终可见的）
- 新增 `api/state.ts` 模块：`postEvent()`, `getViewpointState()`, `getProfile()`

**去重**：后端 `_transition` 已经处理了重复事件（已 confirmed 的 claim 再次 expand 不再产生事件）。

---

### 交互点 3: LINK(v_a, v_b) — confirmed → linked

**触发时机**：用户在侧栏选两个 claims，"Link" → 选 agree/conflict/refine → confirm。

**实现**：新组件 `ClaimLinkPicker`：

```
┌─ Link Claims ──────────────────────────┐
│                                         │
│  From: [Claim 3 from Paper A ▾]        │
│  To:   [Claim 7 from Paper B ▾]        │
│                                         │
│  Relation:  ○ agree  ● conflict  ○ refine│
│  Note:     [________________________]    │
│                                         │
│  [Create Link]                          │
└─────────────────────────────────────────┘
```

**入口**：
- 侧栏 claim 行末的 "🔗" 按钮
- 或者顶部 ActionBar 的 "Link claims" 按钮

**前端改动**：
- 新组件 `ClaimLinkPicker.tsx`
- 新 API 模块扩展 `api/state.ts`: `createLink()`, `deleteLink()`
- 在 `ReadingStation` 侧栏的 claim 列表中渲染 link badge

**signal 链**：`HermesClaimLink.post_save` → confirmed→linked（后端自动，前端无感知）。

---

### 交互点 4: THREAD_WRITE(v) — linked → internalized

**触发时机**：用户在 thread 编辑器中引用一个 claim。

**实现**：新页面 `ThreadPage`（或在现有 NotesPane 加 Thread tab）：

```
┌─ Thread: "Diffusion for video: what matters" ───┐
│                                                    │
│  [Edit title]                                      │
│                                                    │
│  Attached papers: [Paper A ×] [Paper B ×]           │
│                                                    │
│  ── Notes ──                                       │
│  May 4, 14:30                                      │
│  Paper A 的 Claim 3 说的是 temporal consistency     │
│  是关键，但 Paper B 的 Claim 7 用更大的数据集         │
│  证明了相反结论...[more]                             │
│                                                    │
│  Referenced claims:                                │
│  [Claim 3 (Paper A) ×]  [Claim 7 (Paper B) ×]      │
│                                                    │
│  [Add note]  [Attach claim from library...]         │
└────────────────────────────────────────────────────┘
```

**前端改动**：
- 新页面 `ThreadPage.tsx` + route `/threads/:id`
- 侧栏 claim 行的 "📝 Add to thread" 按钮
- 新 API 模块：`createThread()`, `addThreadNote()`, `listThreads()`
- Thread index 入口：navbar 或 ProfilePage

**signal 链**：`POST /api/state/threads/<id>/notes/` 携带 `viewpoint_ids` → 后端 `_transition(..., INTERNALIZED, THREAD_WRITE)`。

---

### 交互点 5: PROFILE_REVIEW — A/C 仪表盘

**触发时机**：用户打开 ProfilePage。

**实现**：新页面 `ProfilePage`：

```
┌─ Profile ──────────────────────────────────────────┐
│                                                     │
│  ┌─ Active Topics ──────────────────────────────┐  │
│  │ diffusion-models     ████████░░ 0.78  ⬆      │  │
│  │ video-generation     ██████░░░░ 0.64  →      │  │
│  │ masked-autoencoders  ████░░░░░░ 0.45  ⬇      │  │
│  │ temporal-consistency ███░░░░░░░ 0.31  ⬆      │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Knowledge Gaps ─────────────────────────────┐  │
│  │ ⚠ You're reading "video diffusion" but       │  │
│  │   haven't covered "score-based models"        │  │
│  │   [Read foundational paper]                   │  │
│  │                                                │  │
│  │ ⚠ "optical flow" — last active 94 days ago    │  │
│  │   [Review canonical paper]                    │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Activity Timeline ──────────────────────────┐  │
│  │                                                │  │
│  │  A(t)  ▁▂▃▄▃▂▁▂▃▄▅▄▃▂▁                      │  │
│  │        Apr 1 ───────────────────── May 4      │  │
│  │                                                │  │
│  │  C(t)  ▁▁▂▂▃▃▃▄▄▄▄▄▄▄▄                      │  │
│  │        Apr 1 ───────────────────── May 4      │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Threads ────────────────────────────────────┐  │
│  │ "Diffusion for video: what matters"  (3 notes)│  │
│  │ "Why ConvNeXt still beats ViT"       (1 note) │  │
│  │ [+ New thread]                                │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Open Questions ─────────────────────────────┐  │
│  │ "Does flow matching actually help for video?" │  │
│  │ "What's the SOTA for precipitation nowcast?"  │  │
│  │ [+ Ask a question]                            │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**前端改动**：
- 新页面 `ProfilePage.tsx` + route `/profile`
- 新 API 模块 `api/state.ts`: `getProfile()`, `getGaps()`, `getActivity()`
- Navbar 加 "Profile" 入口
- 简单图表用纯 CSS/CSS-in-JS 折线（不引入 chart 库——5 个数据点不需要 d3/recharts）

---

## 3. 文件交付清单

### 新增文件

```
frontend/src/
├── api/
│   └── state.ts                     # Hermes API client (profile, events, gaps, links, threads)
├── pages/
│   ├── ProfilePage.tsx              # A/C dashboard + gaps + threads index
│   └── ThreadPage.tsx               # Thread editor with viewpoint references
├── components/
│   ├── ClaimLinkPicker.tsx          # Modal: pick 2 claims + relation type
│   ├── ActivityChart.tsx            # Pure CSS line chart for A(t) + C(t) timelines
│   ├── TopicBar.tsx                 # Horizontal bar: topic name + A score bar
│   ├── GapPanel.tsx                 # Knowledge gap cards with action buttons
│   └── ThreadCard.tsx               # Thread summary card for ProfilePage
└── types/
    └── state.ts                     # ExploreStateDTO, ActivityDTO, GapDTO, etc.
```

### 修改文件

```
frontend/src/
├── App.tsx                          # + route /profile, /threads/:id
├── components/Header.tsx            # + "Profile" nav link
├── pages/ReadingStation.tsx         # + side panel with claim links & thread add
├── components/reading/ClaimCard.tsx # + VIEW_EVIDENCE event on expand
├── components/reading/ActionBar.tsx # + "Link claims" / "Add to thread" buttons
├── components/ClaimCard.tsx         # + VIEW_EVIDENCE event on mount (drawer variant)
└── api/papers.ts                    # (no change needed — existing API is fine)
```

### 后端补充

```
apps/explore/
├── views.py                         # (already exists — 11 endpoints)
├── signals.py                       # FIX: backward transition guard
└── activity.py                      # FIX: topic_id normalization in _batch_viewpoint_to_topic
```

---

## 4. 标准 I/O 与用户迁移

### 导出格式

| 格式 | 内容 | 实现 |
|------|------|------|
| **Zotero .bib** | 所有 read_kept papers + user_notes as `note` field | `GET /api/papers/export/?format=bib` |
| **Markdown** | 每个 thread → 一个 .md 文件，含 claims 引用 | `GET /api/state/threads/<id>/export/` |
| **JSON** | explore_state 全量 dump（vp_states, events, mastery） | `GET /api/state/export/` |
| **PDF** | 保持原始 arXiv PDF 路径不变 — 用户随时可复制 `media/papers/` | 文件系统直接访问 |

### 导入格式

| 格式 | 内容 | 实现 |
|------|------|------|
| **Zotero .bib** | 批量导入论文元数据 + 阅读状态 | `POST /api/papers/import/` — 解析 .bib，创建 Paper + default `new` status |
| **explore_state.json** | 跨设备迁移 explore state | `POST /api/state/import/` |

---

## 5. 实施顺序

| Phase | 内容 | 依赖 |
|-------|------|------|
| **F0** | 修复后端 2 个 bug（backward guard + topic mapping） | 无 |
| **F1** | `api/state.ts` + `types/state.ts` — API client 层 | F0 |
| **F2** | 交互点 1+2: ClaimCard VIEW_EVIDENCE + READ(p) signal | F1 |
| **F3** | `ProfilePage` + 交互点 5: A/C 仪表盘 | F1 |
| **F4** | 交互点 3: `ClaimLinkPicker` | F1 |
| **F5** | 交互点 4: `ThreadPage` + thread notes | F1 |
| **F6** | 阅读器切换: pdf.js → 浏览器原生 `<embed>` | 无 |
| **F7** | 导出/导入: .bib + explore_state.json | F1 |
