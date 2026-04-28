---
pm_id: iter-012
pm_type: iteration
title: Sprint 12 — Paper-centric schema + Inbox verdict（v1.2 地基）
milestone: v1.2
status: in_progress
start_at: 2026-04-28
end_at: 2026-05-04
---

# iter-012 Sprint 12：Paper-centric schema + Inbox verdict

## 战略上下文

4/28 用户拍板 explore-os 产品定位扩展为 **A 进 B 出**：

- A 入口：Subscription brief + Ingest（已有）
- B 沉淀：每篇论文挂 status / comment(history) / tag / paper-level 双链
- 能力切片：内嵌 pdf.js（v1.2 ft-029）+ 导出 Zotero（v1.2 ft-030）+ 桌面通知（ft-031）

本 sprint 是**地基层**：上 user_* 之前必须先抽 Paper 顶层实体。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-028 Paper-centric schema + user_* + Inbox verdict | P0 | in_progress | 主线（约 6 天） |

## Scope

### Backend
- 新建 `apps/papers/`：Paper 模型 + user_status / user_comment / user_tag / user_backlink
- 9 个数据迁移（Paper 表 → 回灌 → FK 加 → 数据 fill → NOT NULL → user 表）
- 既有 `apps/extract/` + `apps/interpret/` 模型加 `paper = ForeignKey(Paper)`
- DRF：扩 `/api/papers/<id>/`（id = key 或 arxiv_id）+ 8 个新 endpoint（status / comments / tags / backlinks）

### Frontend
- `frontend/src/api/papers.ts` 加 9 个 method
- 新组件 `VerdictActions.tsx`：[Skip] [Queue] [Read now]
- `PaperListPage.tsx` 加 status filter chips + 嵌 VerdictActions

## Out of Scope（明确排除）

- ❌ Reading Station 三栏 / pdf.js（→ iter-013 ft-029）
- ❌ comment / tag / backlink **编辑 UI**（→ iter-013 ft-029）
- ❌ FTS5 全文搜 / Zotero export（→ iter-014 ft-030）
- ❌ 桌面通知（→ iter-015 ft-031）
- ❌ claim 级双链（先 paper 颗粒度验证）
- ❌ ft-025 自动更新 + CUDA bundle（→ iter-016）

## 关键决策（已 lock 见 ft-028 spec）

1. Paper-centric schema **彻底重构**（不走"先用 arxiv_id 当 key"短期方案）
2. `Paper.key = [A-Z2-9]{8}` Zotero 风格
3. arxiv_id / doi 降为 Paper 元数据列
4. API path 双 id 接受（key 和 arxiv_id），不破 frontend
5. comment append-only（PATCH 仅可标 hidden）
6. brief 不压抑已决；arxiv v1/v2 不合并

## 工作流分配

| 工作流 | 职责 | Dispatch | 并行 |
|---|---|---|---|
| backend | Paper schema + 迁移 + user_* models + 11 endpoints + tests | **dsp-011** | 与 frontend 并行 |
| frontend | api/papers.ts 扩 + VerdictActions + PaperList filter | **dsp-012** | DTO 已 lock，可 mock |

DTO 契约在 `features/ft-028.md#dto-contracts` 已冻结，两 agent 可并行不互相阻塞。

## 验收

1. 数据迁移完整：本地现有 `fa28a00bdbc067db` Paper 实体被创建，sections/
   figures/tables/equations/claims/evidences 全部迁到 paper_id
2. 既有 `GET /api/papers/<arxiv_id>/` 不破，新增字段 (paper_key/status/tags/n_comments)
3. 8 个新 endpoint 通过 DRF APIClient 测，每个 ≥ 1 happy + 1 edge
4. PaperListPage 默认 status=new；[Queue]/[Skip]/[Read now] 切换生效持久
5. `npm run build` 0 TS error
6. `pytest -q` ≥ 280 passed（基线 262 + 新增）

## 里程碑

| 日 | 内容 |
|---|---|
| D1 (4/29) | dsp-011 backend agent：Paper 模型 + 4 个迁移（Paper / backfill / FK / populate）|
| D2 (4/30) | backend：剩余迁移 + user_* 4 表 + 8 endpoints |
| D3 (5/1) | backend：tests + 主会话 merge + pytest 全过 |
| D2-D4 | dsp-012 frontend agent：api client + VerdictActions + PaperList |
| D5 (5/3) | 主会话集成 + 用户实测 |
| D6 (5/4) | bug 修 + iter 关闭 |

## 风险

- 数据迁移序列 9 步，必须每步可 reverse（subagent 必须实测 forward→reverse 一遍）
- 既有 sources / interpret_v2 / render_* 表是否也要 FK 重接：派发后 backend
  agent 第一步 `grep -r paper_arxiv_id apps/` 列全
- frontend mocking：DTO 已 lock，agent 用 MSW 或简单 mock 即可，不必等
  backend 完成
