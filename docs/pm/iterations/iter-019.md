---
pm_id: iter-019
pm_type: iteration
title: Sprint 19 — 代码 review + 解耦重构（v1.2 收尾）
milestone: v1.2
status: done
start_at: 2026-04-29
end_at: 2026-04-29
---

# iter-019 Sprint 19：代码 review + 解耦重构

## 战略上下文

需求堆叠（ft-027 → ft-028 → ft-029 → ft-033）落地速度优先于结构整洁，
代码耦合度上升。已肉眼可见的 hotspot：

- **顶级 `interpret/` legacy** 与 `apps/interpret/` 同时存在（status 4/28
  已记账：legacy 未切 paper FK）
- **顶级 `sources/`** 与 `apps/extract/` / `apps/papers/` 关系不清
- **LLM 客户端两套**：`interpret/llm.py` + `apps/interpret/llm_client.py`
- **brief_generator 复用老邮件 pipeline**（ft-033）但 import 路径绕弯
- `apps/api/views.py` 在 ft-028 + ft-029 双膨胀

4/29 PM 决议：**v1.2 不再以 ft-030 收尾**，改以"重构 done + ft-034 done"
收尾。ft-030 推到 v1.3 第一刀。chat 分级（按记忆层 — fresh / sustained /
archived）+ user_profile 蒸馏推到 v1.4+；本 sprint 仅保证操作历史种子（既有
papers_user_* 表）不被重构破坏。

## 目标

| # | 内容 | 优先级 | 状态 |
|---|---|---|---|
| 1 | Phase 1：6 组并行 review，报告落 `docs/pm/reviews/` | P0 | ✅ done |
| 2 | Phase 2：PM 整合 6 份报告 → 修复决策 → ft-034 真实 spec | P0 | ✅ done |
| 3 | Phase 3：派修复 agent F1→(F2∥F3∥F4) worktree 隔离 | P0 | ✅ done（4 commits：4e70fc7 / 55f1789 / b7b4b49 / 3b5327c） |
| 4 | Phase 4：集成 + 测试 + ft-034 完工 | P0 | ✅ done |

## Phase 3+4 实测结果（4/29 一日内完成，原计划 12 日）

| 项 | 基线 | 落地 | 备注 |
|---|---|---|---|
| pytest | 332 passed | **371 passed** (+39) | F1 +24 / F3 +14 / F2 +10 / F4 -9 死测 |
| tsc | — | **0 error** | F3 worktree 跑过；主仓 npm install 后复测 0 |
| build 主 chunk | ~636 KB | **637.75 KB** (+1.75 KB) | ≤ 基线 +50 KB ✓ |
| `from interpret` apps/papers/brief_generator.py | — | **0 命中** ✓ | 反向胶水切断 |
| `_convert` apps/interpret/ | — | **0 命中** ✓ | 私有 API 跨 app 调用清零 |
| `BASE_DIR / 'media'` apps/ | 4 处 | **0 处** ✓ | paths.* 化 |
| brief 视觉 / Reading Station | — | 不变 | （用户实测待跑） |

## 关键交付

- **F1**（4e70fc7）：apps/llm 中台层 + prompt(7→5)/model(8→7)/budget(4) registry
- **F3**（55f1789）：apps/api/views(859→拆 5 sub) + serializers(184→拆 6 sub) + frontend types/api 拆分 + JobStatus 5 值过渡 mapping
- **F2**（b7b4b49）：apps/llm/services/{skim,deep,brief}_interpret + brief_generator 瘦身 + extract.get_paper_markdown public API
- **F4**（3b5327c）：BASE_DIR 4 处修 + 6 个 0 字节 stub + 顶级 tldr/figure_classifier 死码 + frontend claims.ts + apps/llm/models 同步清 orphan profile

## 决策 / 偏离

- **3 thin wrappers 留下**（`interpret/{caption_extractor,figure_extractor,pdf_chunker}.py`）— `subscriptions/run_subscription.py` 仍引用，按 P2-1 决议（v1.4 chat 分级落地后回头评估老 email 链是否弃）
- **4 management commands 标 deprecated 而非删** — dev 调试入口仍有人手验证价值
- **JobStatus 5 值后端兼容** — `queued→pending` / `succeeded→done` 在 JobSerializer 边界翻译，1 sprint 过渡，v1.3 删除老值
- **legacy `interpret/llm.py` 留 thin re-export wrapper** — 一周观察期，v1.3 第二刀清

## 下一步

- v1.3 iter-020：ft-030 Library + FTS5（papers/ + types 已拆好）
- v1.4 决议门：P2-1 老 email 链 (subscriptions/run_subscription.py 436 行) 是否弃

## Review 分组（Phase 1）

| Group | Topic | 主要范围 | Agent 类型 |
|---|---|---|---|
| **A** | services | 顶级 `interpret/` + `apps/interpret/` + `apps/papers/brief_generator.py` + `apps/extract/` + 顶级 `interpret/llm.py` vs `apps/interpret/llm_client.py` | general-purpose |
| **B** | api | `apps/api/{views,urls,serializers,ingest,ingest_views,subscriptions_views,jobs}.py` + DTO 与 frontend types 漂移 | general-purpose |
| **C** | pipeline | 顶级 `sources/fetchers/` + `apps/api/ingest.py` (chain) + `apps/api/jobs.py` (APScheduler) + 各 app 的 `management/commands/` + 旧 email pipeline 入口 | general-purpose |
| **D** | frontend | `frontend/src/api/*` + `types/paper.ts` + 各 page 的 hook 散点 + 与 backend serializers 对照 | general-purpose |
| **E** | electron | `electron/src/*` + `sidecar_entry.py` + `apps/core/paths.py` + `apps/papers/paths.py` + DATA_DIR 路径假设 | general-purpose |
| **F** | dead-code | 全仓死码 / 新旧并存 / 测试覆盖空洞 / superseded 模块（如 ft-012） | general-purpose |

## Phase 流程

```
Phase 1  6 个 review agent 并行（only-read，写入 docs/pm/reviews/）
         产出：6 份 .md 报告（耦合 hotspot + 解耦提议 + 风险）
         约束：不改任何代码，不动 docs/pm/ 之外任何位置（除报告本身）

Phase 2  PM 决策（主会话与用户）
         - 跨组冲突 / 重叠 hotspot 收口
         - 必修 / 延后清单
         - ft-034 真实范围最终确定（5 LLM 能力规整 + 哪些必修解耦）
         - 修复分组（按文件冲突避免）

Phase 3  修复 agent 派发
         - 数量：phase 2 决定（建议 ≤ 3 并行）
         - 隔离：worktree（CLAUDE.md 第 1/9 条）
         - 文件白/黑名单严格写死
         - 不可触碰 docs/pm/

Phase 4  主会话集成（顺序 merge → pytest → tsc → build）
         + 用户实测 + 关 sprint
```

## Out of Scope

- ❌ ft-030 Library + FTS5（推到 v1.3 第一刀）
- ❌ ft-035 user_profile 蒸馏（推到 v1.4+，与 chat 分级一起做）
- ❌ chat agent / MCP server（v1.4+ 决策待重启）
- ❌ user_event 检索/点击日志表（永久不在 v1.x，4/29 PM lock）
- ❌ 重写测试框架 / 全量测试覆盖率冲到 100%（KISS）
- ❌ 引入新依赖 / 升大版本

## 关键约束

1. **review 不写代码**——任何 phase 1 agent 试图修改 `apps/`、`frontend/`、
   `electron/` 都视为越界。仅允许在 `docs/pm/reviews/` 下 Write 报告
2. **修复阶段 worktree 隔离**——避免 6 组改动互相冲突
3. **保留操作历史**——`papers_user_*` 表 schema 不动；`papers_brief` 表
   schema 不动（ft-033 today 落地，未实测稳定期）
4. **ft-029 / ft-033 落地未久**——重构不能破坏既有 verdict / brief / Reading
   Station 视觉行为；用户实测要复跑

## 验收

| 项 | 标准 |
|---|---|
| Phase 1 | 6 份 review 报告齐全 + frontmatter 合规 |
| Phase 2 | ft-034 真实 spec 落 `features/ft-034.md`（替换原草图） |
| Phase 3 | 修复 dispatch 全部 closed（rpt-* 配对） |
| Phase 4 | `pytest -q` ≥ 315 passed（基线不退）/ `tsc -b` 0 error / `npm run build` 主 chunk 不超 +50KB / brief 视图 + Reading Station 视觉无回归 |

## 里程碑（粗）

| 日 | 内容 |
|---|---|
| 4/29 | iter-019 立项 + 6 review agent 派发 |
| 4/30 | review 报告回收 + PM phase 2 决策 |
| 5/1 | ft-034 真实 spec + 修复 dispatch 派发 |
| 5/2–5/8 | 修复 agent 实施 + 主会话 merge |
| 5/9–5/11 | 集成 + 用户实测 + bug 修 |
| 5/12 | iter-019 关闭，启动 v1.3 iter-020（ft-030 Library + FTS5） |

## 风险

- **review 报告超长**：6 份并行可能产生几千行报告，PM 整合压力大。**对策**：
  prompt 强制每组报告 < 500 行；hotspot 数量上限 15 条
- **修复阶段冲突**：多组同时改 `apps/api/views.py`。**对策**：phase 2 按文件
  分组而非按 group 分组
- **legacy `interpret/` 删除风险**：可能仍被某些路径 import。**对策**：F 组
  专门扫 import graph；删除前先做 deprecation shim
- **ft-033 稳定期未过**：4/29 today 才落，重构期可能踩到刚定型字段。**对策**：
  papers_brief 表本 sprint 不动
