---
pm_id: iter-007
pm_type: iteration
title: Sprint 7 — Electron 基础设施清理 + DRF API
milestone: v0.9
status: done
start_at: 2026-04-26
end_at: 2026-04-26
---

# iter-007 Sprint 7：Electron 基础设施清理 + DRF API

## 战略上下文

iter-006 ft-021 落地的 cluster cards 实测可读性不及 HTML 邮件渲染。
2026-04-26 二次决策：**图谱可视化推迟到 v1.x**，v0.8 索引层数据建立完成已是
后续视图的真正资产。从 v0.9 起 Electron 直上 ——HTML+KaTeX+React 才是
精读视图正确形态。

本 sprint 是 Electron 桌面化的**第一步**：清理单机化耦合 + 把现有 CLI
包装成 DRF API endpoints，为 ft-023 Electron shell + sidecar 铺路。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-022 Electron 基础设施清理 + DRF API | P0 | in_progress | 主线 |

## Scope

- **EXPLORE_OS_DATA_DIR 抽象**：消除 frozen exe 中 `BASE_DIR` 不可写
  - `apps/core/paths.py` 集中管理（papers / figures / render / cache / outbox）
  - 替换全项目 hardcoded `BASE_DIR / "media"`
- **SMTP fallback**：`EMAIL_HOST=""` 时写 `.eml` 到 `DATA_DIR/outbox/`
- **APScheduler in-process**：`apps/core/scheduler.py` 单例 BackgroundScheduler
- **docling 模型缓存重定位**：`HF_HOME` / `TRANSFORMERS_CACHE` 走 `DATA_DIR/cache/huggingface`
- **DRF API 包装现有 CLI**：
  - `apps/api/` 新建 Django app
  - 8 个 endpoint：papers list/detail/markdown/figure/graph/claims + extract/interpret/render trigger + jobs status + health
  - 复用 4 个 management command 业务逻辑

## Out of Scope

- ❌ Electron shell（→ ft-023 / iter-008）
- ❌ 前端 UI（→ ft-024 / iter-009）
- ❌ PyInstaller 打包（→ ft-023）
- ❌ 自动更新（→ ft-025）
- ❌ 图谱可视化（推迟到 v1.x）

## 关键设计决策（已 lock）

1. 同库前缀 `core_*`（如有）/ `api_*`（如有）
2. `apps/core/paths.py` 是路径单一来源，**所有持久化路径必须通过它**
3. APScheduler `BackgroundScheduler`（不是 Blocking），任务用 `transaction.atomic()`
4. DRF endpoint 异步化：`POST /extract` 立即返回 `{job_id, status:queued}`，job 状态查 `/jobs/<id>`
5. 路径切换不破现有 CLI：`extract_paper` / `interpret_paper` / `render_graph` / `run_subscription` 全部仍能跑

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| backend-core | ft-022 EXPLORE_OS_DATA_DIR + paths + scheduler + DRF API | dsp-006 |

## 验收

- 设置 `EXPLORE_OS_DATA_DIR=/tmp/test` 后所有数据写入该目录
- `EMAIL_HOST=""` 时 run_subscription 写 `.eml` 到 outbox/
- APScheduler 启 sidecar 时自动注册 jobs，`/api/health` OK
- 8 个 DRF endpoint 用 DRF APIClient 测全过
- 全量回归 pytest 通过（不少于 214 + 新测试）
- 既有 CLI 不破

## 风险

- **路径替换涉及多文件**：用 `git grep "BASE_DIR.*media"` 完整扫一遍
- **APScheduler × Django ORM thread safety**：任务函数内部 `transaction.atomic()`
- **HF_HOME 重定向时机**：必须在 import docling 之前；放在 `apps/core/paths.py` 顶部

## 里程碑

- W1 D1-2: paths 模块 + 替换硬编码 + outbox fallback
- W1 D3-4: APScheduler + 健康检查
- W1 D5: DRF API 8 endpoint + 测试
- W1 D6-7: 联调 + buffer

## 每日进展

_(按日追加)_
