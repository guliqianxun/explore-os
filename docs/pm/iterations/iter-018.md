---
pm_id: iter-018
pm_type: iteration
title: Sprint 18 — Brief 内容处理层（ft-033）
milestone: v1.2
status: planned
start_at: 2026-04-30
end_at: 2026-05-03
---

# iter-018 Sprint 18：Brief 内容处理层

## 战略上下文

ft-029 上线后用户实测发现 Today's brief 视图卡片"空白"——只有 title + 元数据，没有任何叙述文字。

根因（4/29）：`apps/papers/Paper` 没有 abstract / tldr / 翻译字段；老邮件渲染（ft-006/009/014）的 skim_interpret + deep_interpret pipeline 没接到新 ingest 链。

本 sprint **不重写**老 pipeline，只在 apps 层加缓存壳（PaperBrief 表）让数据落 SQLite，BriefView / detail 都能吃到同一份缓存。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-033 Brief 内容处理层 | P0 | planned | ~2.5 天 |

## Scope

### Backend
- `Paper.abstract` 字段 + 0005 migration + 0006 backfill (从 docling abstract section)
- `PaperBrief` OneToOne 表 + 0007 migration
- `apps/papers/brief_generator.py` 复用 `interpret/interpretation.py` 的 skim/deep_interpret + perspective 解析
- 2 endpoints：POST regenerate / GET brief
- DTO: list 加 `tldr_zh / keywords / has_brief`；detail nested `brief`
- ingest 链 abstract 自动填充
- ~6 例测试

### Frontend
- types/paper.ts 扩 PaperBrief / 三个 list/detail 字段
- BriefView 三 card 接通 lead = tldr_zh，主要论文卡加 keywords chips
- PaperDetail [Generate brief] 按钮 + brief 折叠区显示 for_you / key_innovation

## Out of Scope（明确排除）

- ❌ deep_interpret 升级（method_summary 实质能力 → 留 ft-014 延续）
- ❌ Per-paper perspective override（v1.3+）
- ❌ 自动 ingest 后跑 brief（默认手动）
- ❌ 批量 regenerate / brief 历史版本
- ❌ 跨 paper narrative（ft-010 领地）

## 关键决策（已 lock 见 ft-033 spec）

详见 `features/ft-033.md#决策`。

## 工作流分配

主会话直接做（工作量 2.5 天，无需派 subagent）。先 backend → DTO 锁 → frontend 串行。

## 验收

详见 `features/ft-033.md#验收`（10 项）。

## 里程碑

| 日 | 内容 |
|---|---|
| D1 (4/30) | Paper.abstract 字段 + 2 migration + 回填 + ingest 集成 |
| D2 (5/1) | PaperBrief 表 + brief_generator + 2 endpoints + 6 测试；DTO 注入 |
| D3 (5/2) | frontend types + BriefView 三 card 接通 + Generate 按钮 + brief 折叠区 |
| D4 (5/3) | 集成 + 用户实测 + bug 修；iter 关闭，预告 iter-014 ft-030 |

## 风险

- LLM 调用失控：默认手动触发，用户批量点 regenerate 仍可能消耗大；考虑后续接 ft-008 budget
- abstract 回填来源：docling 第一 section 不一定是 abstract——fallback path icontains 'abstract' → ordinal=1
- deep_interpret 占位返回：ft-014 真正能力是另一个 ft 的工作；本 sprint 字段空着仍能跑
- skim_interpret 依赖 abstract：abstract 空 → skim 返回 None → 前端 fallback title

## 与其他 ft 关系

- 依赖 ft-029（已 ✅）
- 复用 `interpret/interpretation.py`（不动）
- 不冲突 ft-032（修订层 vs 内容层）
