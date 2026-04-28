---
pm_id: iter-013
pm_type: iteration
title: Sprint 13 — Reading Station + ClaimCard 引文展开（ft-029）
milestone: v1.2
status: planned
start_at: 2026-04-29
end_at: 2026-05-07
---

# iter-013 Sprint 13：Reading Station + ClaimCard 引文展开

## 战略上下文

iter-012 落地 Paper-centric schema + user_* 4 表 + Inbox verdict UI（ft-028 ✅）。
本 sprint 上层建：把"打开一篇 paper 深读"的体验做出来，并补 ft-028 实测发现的
verdict 出口 gap（read_kept / archived）。

4/28 PM review 决议（见 CHANGELOG）：
- ClaimCard 三态（含**引文展开附原文**）并入本 ft，无 schema 改动
- 编辑态移交 ft-032，本 ft 仅 placeholder
- bottom action bar **状态机驱动 + 纯文字**（无图标）
- NotesPane 响应式宽度（min 280 / max 420 / 窄屏抽屉）
- 顶部 status pill 双入口直跳

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-029 Reading Station + ClaimCard 引文展开 | P0 | planned | 主线（约 8 天） |

## Scope

### Backend
- `Paper.pdf_path` 字段 + ingest 自动填充 + 迁移
- `GET /api/papers/<id>/pdf/` FileResponse + HEAD 探测
- `PaperDetailSerializer.claims[]` 加 `evidences` nested（material_id + relation）
- 测试 ~3 例

### Frontend
- 依赖：`react-pdf@9` + `react-resizable-panels@2`
- `PaperDetailPage` 改壳分发：station / speed mode
- `ReadingStation`：3 栏响应式 + 窄屏抽屉
- `SpeedCardPane`：复用既有速读卡
- **`ClaimCard` 三态**：collapsed / expanded with evidence / editing(placeholder)
  - 引文展开 fan-out 5 类 material（不同模板）
  - `[→ jump in PDF]` 联动
- `PdfViewer`：react-pdf + bbox overlay + textLayer 搜索
- `NotesPane`：Comments / Tags / Backlinks 三 tab
- bottom action bar 状态机驱动（reading / read_*/archived 不同按钮组）
- 顶部 status pill 双入口
- code-split：reading station 路由懒加载

## Out of Scope（明确排除）

- ❌ ClaimCard 用户编辑 / hide（→ iter-017 ft-032）
- ❌ wiki-link `[[KEY]]` 语法（永久不做）
- ❌ Chat with PDF（永久不做）
- ❌ in-PDF 标注（永久不做）
- ❌ FTS5 全文搜 / Zotero export（→ iter-014 ft-030）
- ❌ 桌面通知（→ iter-015 ft-031）
- ❌ Range request / 渐进 PDF 加载（KISS）

## 关键决策（已 lock 见 ft-029 spec）

详见 `features/ft-029.md#决策`。本 sprint 不再 re-open。

## 工作流分配

| 工作流 | 职责 | Dispatch | 并行 |
|---|---|---|---|
| backend | Paper.pdf_path + ingest fill + PDF serve + evidences nested + tests | **dsp-013** | 与 frontend 并行 |
| frontend | ReadingStation + PdfViewer + NotesPane + ClaimCard 三态 + 状态机 action bar + status pill | **dsp-014** | DTO 已 lock，可 mock |

DTO 契约在 `features/ft-029.md#接口契约 + #ClaimCard 三态` 已冻结。frontend agent 单 agent 不可拆（PdfViewer / NotesPane / Layout / ClaimCard 高耦合）。

## 验收

1. 进 `/papers/<id>` 默认 station 模式（如有 PDF）
2. ClaimCard `▸` 展开附原文：5 类 material 模板正确
3. `[→ jump in PDF]` 联动：figure → 跳页 + bbox 高亮 / section → textLayer 搜索
4. NotesPane 三 tab 都能 CRUD（comment append-only / tag / backlink）
5. 进 station 自动 status: queued/new → reading
6. bottom action bar 状态机驱动：reading 4 键 / read_*/archived 简化
7. 顶部 status pill 下拉直跳，受 STATUS_TRANSITIONS 约束
8. NotesPane 响应式：宽屏右栏 / 窄屏 < 1100px 抽屉
9. PDF 不可用时降级 2 栏（speed-card 60% + notes 40%）
10. resize 持久（autoSaveId）
11. `npm run build` 0 TS error，主 chunk 不超过 ft-028 +50KB
12. `pytest -q` ≥ 309（306 + 新增 ~3）

## 里程碑

| 日 | 内容 |
|---|---|
| D1 (4/29) | dsp-013 backend：Paper.pdf_path + 迁移 + ingest fill + PDF serve |
| D2 (4/30) | backend：evidences nested DTO + 3 测；主会话 merge |
| D2–D7 | dsp-014 frontend：deps + PdfViewer hello-world → 三栏布局 → ClaimCard 三态 → NotesPane → action bar → status pill |
| D8 (5/6) | 主会话集成 + 用户实测 |
| D9 (5/7) | bug 修 + iter 关闭；预告 iter-014 ft-030 |

## 风险

- pdf.js bundle 体量（详见 ft-029 §风险 1）
- worker 配置 cross-platform（Electron file://）
- bbox 坐标系转换（PDF points 左下 vs canvas px 左上）
- frontend agent 必须先做 hello-world 验证 pdf.js 加载再继续
- 用户实测时 ClaimCard 编辑诉求若强烈，立即排期 iter-017 ft-032
