---
pm_id: iter-010
pm_type: iteration
title: Sprint 10 — 前端编辑/杂志重设计
milestone: v1.1
status: in_progress
start_at: 2026-04-27
end_at: 2026-04-30
---

# iter-010 Sprint 10：前端编辑/杂志重设计

## 战略上下文

iter-009 ft-024 落地 4 页 MVP 并本机实测后，UX 反馈：现状像 SaaS admin
后台，不是论文阅读工具。三栏 IDE 布局对功能友好但反沉浸；PaperList 像
表不像 feed；shadcn 默认风格无品牌识别。

2026-04-27 决策：**Editorial / Magazine 方向**重设计前端表现层。架构 / API /
ClaimCard 数据结构 / Electron sidecar 全部不动，只重做 layout + typography +
色彩 + 沉浸模式。

ft-025（自动更新 + CUDA/CPU 双轨）推到 iter-011。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-026 前端编辑/杂志重设计 | P0 | in_progress | 主线（约 3 天） |

## Scope

- PaperListPage → editorial feed（日期分组 + hero + lead paragraph）
- PaperDetailPage → 单栏沉浸 + 右抽屉 ClaimDrawer + 左浮动 FloatingTOC
- 衬线正文（Source Serif 4 / 思源宋体）+ 无衬线 UI（Inter）
- 色板：暖中性 + 单 accent
- ReadingModeToggle 一键沉浸
- CORS 修复（django-cors-headers）

## Out of Scope

- ❌ 暗色模式（v1.x）
- ❌ 国际化
- ❌ 改 ClaimCard 数据结构
- ❌ 改 API / sidecar / Electron 主进程
- ❌ ft-025 自动更新（→ iter-011）

## 关键设计决策（已 lock）

1. 方向：Editorial / Magazine（Distill × Stratechery）
2. 默认沉浸：PaperDetail 单栏阅读，claims 折叠到右抽屉
3. 调性：严肃学术 × 温暖人文
4. CORS 修复走 Django `django-cors-headers`（B 方案，比 webSecurity:false 通用）
5. 复用全部 ft-024 现有组件（ClaimCard / MarkdownView / EquationBlock 等），只改样式与容器

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| frontend-design | ft-026 editorial 重设计 + CORS 修复 | dsp-009 |

## 验收

- 默认进 PaperDetail 是单栏沉浸阅读，公式真渲染 + 行高 1.7+
- ClaimDrawer 右侧滑入，宽度 480-600px，公式/红条/cite 宽松
- PaperListPage 是 feed 不是表
- CORS 修复后实际能拉数据，无 Network Error
- `npm run build` 0 TS error
- 既有 pytest ≥ 241

## 风险

- 字体 bundle 变大（Source Serif）：用 woff2 + subset，prod 可考虑 system fallback
- 抽屉动画 + 沉浸切换：Tailwind transition 够用

## 里程碑

- D1: tokens + 字体 + PaperListPage feed
- D2: PaperDetailPage 沉浸 + ClaimDrawer + FloatingTOC + ReadingMode
- D3: CORS + 联调 + 实战实拍

## 每日进展

_(按日追加)_
