---
pm_id: iter-005
pm_type: iteration
title: Sprint 5 — 解读器 L1+L2 生产侧
milestone: v0.7
status: done
start_at: 2026-04-26
end_at: 2026-04-26
---

# iter-005 Sprint 5：解读器 L1+L2（生产侧）

## 战略上下文

iter-004 完成抽取层底座（ft-019 接口契约 + ft-015 Docling 实现 + 双栏清洁层）。
本 sprint 在抽取层之上做**结构化解读**——把论文从「材料堆」升级为「带逻辑链 + 反向信号的可寻址知识」。

**范围收口**：本 sprint 只做生产侧（产出 claims/evidence/signals 落库 + CLI），**不动 legacy interpret/* 消费者**（deep_interpret / figure_picker 接入 L1+L2 留 ft-024）。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-020 解读器 L1+L2 生产侧 | P0 | in_progress | 主线 |

## Scope

- 新建 `apps/interpret/` Django app（与 legacy `interpret/` 并存，db_table 前缀 `interpret_*`）
- 三张表：`interpret_claims` / `interpret_claim_evidence` / `interpret_counter_signals`
- L1：claim 抽取 + evidence 强制 cite material_id
- L2：论文内反向信号扫描（限定 limitation / ablation 段，不引外部 prior work）
- CLI：`python manage.py interpret_paper <arxiv_id>`
- 复用 `interpret/llm.py:chat()` 调 LLM；mock 测试策略与 ft-015 一致

## Out of Scope

- ❌ legacy `interpret/deep_interpret.py` 接入 L1+L2（→ ft-024）
- ❌ `figure_picker` 改用 claims 反查 evidence figure（→ ft-024）
- ❌ `run_subscription` 主流程切到 L1+L2 走料（→ ft-024）
- ❌ 跨篇 claim 关联（→ v1.x）
- ❌ 引用论文外 prior work 做批判（暂禁）
- ❌ ft-021 渲染分级 + drawio（→ iter-006）

## 关键设计决策（已 lock）

1. **Material catalog 作为 LLM 上下文**：从 `extract_*` 表组装 `[§:N] / [fig:N] / [tbl:N] / [eq:N]` 索引清单
2. **正文走 Docling markdown**：调 `apps.extract.extractors.docling_ext._convert()` 复用缓存，`doc.export_to_markdown()` 拿全文
3. **强制 cite**：LLM 返回未挂 material_id 的 claim 直接丢弃（记日志）
4. **L2 挂载约束**：每条 counter_signal 必须有 `claim_id` + `evidence_material_id`（schema 强制）
5. **同库不同前缀**：表名 `interpret_*`，避免 PG-only 字段
6. **LLM 测试全 mock**：与 ft-015 docling 一致，单测不真调

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| backend-interpret | ft-020 L1+L2 生产侧（models + interpreter + CLI + tests） | dsp-004 |

## 验收

- `python manage.py interpret_paper leworldmodel` 跑通：产出 5-15 claims（每条 cite ≥1 material）+ ≥1 counter_signal
- 同篇 ConvNeXt V2 同样跑通
- 全量 pytest 绿（不少于 151 + 新测试）
- 既有 `run_subscription` 不破（legacy 路径不动）
- ruff 通过

## 风险

- **LLM 输出格式漂移**：用 `response_format={"type":"json_object"}` 强约束 + 后处理 try/except 兜底
- **token 超限**：长论文 markdown 切块（按 section 切），每块抽 claims 后合并去重
- **claim 抽取偏离原文**：每条 claim 强制 cite material_id 才入库；LLM 自评 confidence < 0.5 丢弃
- **DashScope LLM 成本**：本 sprint 实战仅 2 篇（leworldmodel / convnextv2），预算阈值 LLM_DAILY_BUDGET_CNY 已生效

## 里程碑

- W1: models + Interpreter 接口骨架 + LLM prompt + L1 claim 抽取 + cite 校验
- W1: L2 反向信号扫描（limitation + ablation 双路径）
- W2: CLI + 实战两篇 + 测试覆盖

## 每日进展

_(按日追加)_
