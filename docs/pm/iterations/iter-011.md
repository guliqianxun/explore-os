---
pm_id: iter-011
pm_type: iteration
title: Sprint 11 — Subscription 表单化 + Ingest 入口
milestone: v1.1
status: done
start_at: 2026-04-27
end_at: 2026-04-27
---

# iter-011 Sprint 11：Subscription 表单化 + Ingest

## 战略上下文

iter-010 ft-026 编辑/杂志重设计落地后用户实测反馈：PaperList 形态满意，但
SubscriptionPage 仍是 yaml textarea 不友好，RunPage 定位不清。
本 sprint 重做这两页 + 加 PDF/arxiv/URL ingest 后端。

ft-025（自动更新 + CUDA/CPU 双轨）推到 iter-012。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-027 Subscription 表单化 + RunPage → Ingest | P0 | in_progress | 主线（约 3 天） |

## Scope

- Backend：5 subscription CRUD/run + 3 ingest endpoints (upload / arxiv / url) + chain extract→interpret→render
- Frontend：SubscriptionPage 卡片+表单 modal + RunPage → IngestPage 三入口

## Out of Scope

- ❌ Subscription 切 DB（YAML 保留）
- ❌ 多用户 / 高级 cron 编辑器
- ❌ ingest 后自定义标签
- ❌ ft-025 自动更新（→ iter-012）

## 关键设计决策（已 lock）
1. YAML 不动
2. 三种 ingest 都支持（PDF / arXiv / URL）
3. Run subscription 按钮移到 SubscriptionCard
4. ruamel.yaml 替 PyYAML 保留注释（如未装则加）
5. URL ingest 限 PDF content-type，不限域

## 工作流分配
| 工作流 | 职责 | Dispatch |
|---|---|---|
| backend+frontend | ft-027 整套 | dsp-010 |

## 验收
- SubscriptionPage 卡片+modal+yaml advanced
- IngestPage 三入口实测可跑通
- chain job 三阶段状态可见
- npm build 0 error / pytest ≥ 241

## 里程碑
- D1: backend 8 endpoints + chain
- D2: frontend SubscriptionPage 重做
- D3: frontend IngestPage + 实战

## 收尾

**单日完成**（2026-04-27 一气拿下，commits `7fc7075` + `ffc27a7`）。

**PM 漂移更正**（2026-04-30）：本 iter 实际在 2026-04-27 已完成，但 status 一
直挂 in_progress 到 iter-020 复盘时才同步。期间 iter-012/018/019/020 都基于本
iter 交付的 SubscriptionPage / IngestPage 继续工作，事实上把本 iter 当 done。
end_at 同步更正为 2026-04-27。详见 ft-027.md 落地段。
