---
pm_id: iter-009
pm_type: iteration
title: Sprint 9 — 前端 MVP 4 页（Vite + React + Tailwind + shadcn/ui + KaTeX）
milestone: v1.1
status: in_progress
start_at: 2026-04-26
end_at: 2026-05-10
---

# iter-009 Sprint 9：前端 MVP 4 页

## 战略上下文

iter-007 ft-022 + iter-008 ft-023 已落地 DRF API + Electron shell + sidecar，
本机实测 9 endpoint + 端口握手 + 进程清理全通。本 sprint 把空 BrowserWindow
变为可日用的 4 页 MVP，让 explore-os 真正成为桌面 app。

**图谱可视化推迟到 v1.x（决策已锁定）**：右栏不嵌 Excalidraw，改为纯 React
ClaimCard + react-katex 真渲染公式 + 跳转高亮。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-024 前端 MVP 4 页 | P0 | in_progress | 主线（最大 ft，~2 周） |

## Scope

- `frontend/` 整目录（Vite + React + TS + Tailwind + shadcn/ui）
- 4 页：PaperListPage / PaperDetailPage / SubscriptionPage / RunPage
- `ClaimCard` 核心组件（KaTeX BlockMath + counter_signal 红条 + cite badges）
- `MarkdownView` 中栏（react-markdown + rehype-katex + image 内嵌）
- API client（axios + TanStack Query），baseURL 从 `window.explore.getBackendPort()` 拿
- Electron 主进程改：placeholder.html → frontend/dist/index.html（prod）/ Vite dev server URL（dev）

## 顺手修两个 ft-023 follow-up（dispatch 内一并完成）

1. `electron/src/main.ts` 加 `app.setName("explore-os")` 让 `userData` 走 `%APPDATA%/explore-os` 而非默认 `Electron`
2. `sidecar_entry.py` 在 `django.setup()` 前显式 `os.environ["DATABASE_URL"] = f"sqlite:///{data_dir}/explore_os.sqlite3"`，避免 .env DATABASE_URL 在桌面端覆盖 DATA_DIR 路径

## Out of Scope

- ❌ 跨篇 narrative 视图 / 用户编辑 claims（→ v1.x）
- ❌ 国际化 / 暗色模式 toggle（默认亮色，shadcn 自带 toggle 可加但不阻塞）
- ❌ 桌面通知 / 系统托盘 / 多窗口
- ❌ 自动更新（→ ft-025）
- ❌ 图谱可视化（永久推迟到 v1.x，不改这条）

## 关键设计决策（已 lock）

1. **前端栈**：Vite 5 + React 18 + TypeScript 5 + Tailwind 3 + shadcn/ui + Zustand + TanStack Query + React Router 6 + react-katex + react-markdown
2. **ClaimCard 取代 Excalidraw 嵌入**：右栏纯 HTML，equation 走 `<BlockMath>`，counter_signal 红条内嵌，cite badges 可点击跳转中栏 markdown
3. **三栏布局**：左 sections 树（250px 固定）/ 中 markdown（flex）/ 右 ClaimList（400px 固定）
4. **dev / prod 双模式**：dev 加载 `VITE_DEV_SERVER_URL`，prod 加载 `frontend/dist/index.html`
5. **shadcn/ui 是 cp 到本地的代码**（不是 npm 包），`frontend/src/components/ui/` 全 commit

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| frontend-mvp | ft-024 4 页 + ClaimCard + MarkdownView + ft-023 两个 follow-up | dsp-008 |

## 验收

- `cd frontend && npm install && npm run build` 产 `frontend/dist/` 静态资源
- `cd frontend && npm run dev` 起 Vite dev server (默认 5173)
- `cd electron && npm run dev:electron`（带 `VITE_DEV_SERVER_URL=http://127.0.0.1:5173`）→ Electron 加载前端 + 联通 sidecar
- 4 页都能访问 + 数据正确：
  - PaperListPage 列出 leworldmodel/convnextv2 两篇
  - PaperDetailPage 三栏布局，ClaimCard 公式真渲染
  - SubscriptionPage 列订阅 + 编辑
  - RunPage 触发 + 状态轮询
- 既有 Python 测试不破（241+）
- TS 类型检查通过：`npm run build` 0 error

## 风险

- **shadcn/ui 初始化**：`npx shadcn-ui@latest init` 需要交互；用 `--yes` flag + 预置 `components.json`
- **Tailwind 4 vs 3**：用 Tailwind 3（Vite 整合最稳）
- **react-katex peer**：要装 `katex` 本身 + `react-katex`，import css
- **PaperDetailPage 三栏联动**：先做单向（claim → markdown 滚动），双向留 v1.x
- **shadcn/ui 不是 npm 包**：cp 到本地的代码要 commit，volume 不大但要纳入 PR
- **Electron prod 加载本地文件**：`mainWindow.loadFile(...)` 路径要对齐 electron-builder 的 `files` 配置

## 里程碑

- W1 D1: Vite + React + TS + Tailwind + shadcn/ui 脚手架 + Router
- W1 D2-3: PaperListPage + 列表布局 + API client
- W1 D4-7: PaperDetailPage（最重）—— 三栏 + ClaimCard + MarkdownView + 联动
- W2 D1-2: SubscriptionPage + RunPage + ft-023 follow-up
- W2 D3-5: 联调 + Electron prod 加载本地 dist + buffer

## 每日进展

_(按日追加)_
