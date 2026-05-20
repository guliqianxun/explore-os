---
pm_id: iter-023
pm_type: iteration
title: Sprint 23 — 记忆/编排双层 H0（观点状态机 + 事件日志 + topic 种子）
milestone: v1.4
status: done
start_at: 2026-05-04
end_at: 2026-05-07
---

# iter-023 Sprint 23：记忆/编排双层 H0 落地

## 战略上下文

ft-041 记忆/编排双层设计已完成（`docs/design/explore-os-formal-spec.md` v0.2 + `docs/design/explore-os-architecture.md`）。
核心原子是观点 (viewpoint / claim) 的五态状态机：unseen → exposed → confirmed → linked → internalized。

本 sprint 是 Hermes 最小可积累单元：建事件日志和状态表，开始积累数据。
不建任何派生计算——$A$/$C$/Gap 在数据充足后再做。

## 目标

| # | Feature | 优先级 | 状态 |
|---|---------|--------|------|
| 1 | ft-041 H0: 观点状态机 + 事件日志 + topic 种子 | P0 | planned |

## Scope

### 1. Django app `apps/hermes/`

- `models.py`: 9 张表（`hermes_` 前缀）
  - `HermesVPState`, `HermesVPEvent`, `HermesTopic`, `HermesTopicEdge`
  - `HermesActivity`, `HermesClaimLink`, `HermesThread`, `HermesThreadNote`
  - `HermesOpenQuestion`
- `signals.py`: 3 个 signal handler
  - `UserPaperStatus.post_save` → unseen→exposed
  - `HermesClaimLink.post_save` → confirmed→linked
  - `HermesClaimLink.post_delete` → linked→confirmed
- `activity.py`: `compute_activity()` + `compute_consolidation()` 函数
- `crunch.py`: `run_crunch()` 编排器（手动触发，未来接 APScheduler）
- `views.py` + `urls.py`: 11 个 API endpoint
- mgmt commands: `crunch`, `seed_topics`

### 2. 注册 + 迁移

- `config/settings.py` INSTALLED_APPS 添加 `apps.hermes`
- `makemigrations` + `migrate`
- 验证表结构创建成功

### 3. 种子数据

- `python manage.py seed_topics` — 从已有 papers 种 topic
- 验证 `hermes_topic` 表有数据

### 4. 单元测试

- `apps/hermes/tests_models.py`: 表创建 + unique constraints
- `apps/hermes/tests_signals.py`: 状态迁移正确性
- `apps/hermes/tests_activity.py`: $A$ / $C$ 计算一致性

## 验收标准

- [ ] `hermes_vp_state` 表存在，unique (user, viewpoint_id)
- [ ] 用户标记 paper 为 reading → 对应 viewpoints unseen → exposed
- [ ] `hermes_vp_event` 每步迁移有对应事件行
- [ ] `seed_topics` 产出的 topic 数 > 0
- [ ] `crunch` 命令不报错
- [ ] `GET /api/hermes/profile/` 返回合法 JSON
- [ ] pytest 全部通过

## 各域 WIP 快照

| 域 | WIP 数 | 限制 | 状态 |
|----|--------|------|------|
| backend | 1 | 3 | ✅ |
| frontend | 0 | 3 | ✅ |

## 结转项

| Feature | 域 | 原因 | 下个迭代 |
|---------|-----|------|---------|
| — | — | — | — |
