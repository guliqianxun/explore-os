---
pm_id: iter-008
pm_type: iteration
title: Sprint 8 — Electron shell + Python sidecar
milestone: v1.0
status: in_progress
start_at: 2026-04-26
end_at: 2026-05-03
---

# iter-008 Sprint 8：Electron shell + Python sidecar

## 战略上下文

iter-007 ft-022 已就绪 DRF API + EXPLORE_OS_DATA_DIR 抽象 + APScheduler。
本 sprint 把 Electron 壳搭起来，让 explore-os 作为本地 desktop app 启动：
Electron 主进程 + waitress 跑 Django sidecar + HTTP localhost 通信。

**本 sprint 不含前端 UI**——一个空 BrowserWindow（dev 时加载 Vite，prod 时加载占位）。
前端 MVP 留 ft-024。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-023 Electron shell + Python sidecar + PyInstaller | P0 | in_progress | 主线 |

## Scope

- `electron/` 目录：package.json + tsconfig + src/{main,preload,sidecar,port}.ts
- `sidecar_entry.py`（项目根）：Waitress 跑 Django，--port / --data-dir 参数
- `build/sidecar-cuda.spec` PyInstaller spec（CUDA 版自用）
- `build/electron-builder.yml`
- npm scripts：dev:sidecar / dev:electron / build:sidecar / build:electron / build:all
- `pyproject.toml` dev-dep 加 `pyinstaller>=6.10` + `waitress>=3.0`

## Out of Scope

- ❌ 前端 UI（→ ft-024）
- ❌ CPU 版 PyInstaller spec（→ ft-025）
- ❌ 自动更新 / 代码签名（→ ft-025 / v1.x）
- ❌ macOS DMG 美化 / Windows installer 定制
- ❌ npm install / PyInstaller bundle 实测（沙箱限制，用户本机验证）

## 关键设计决策（已 lock）

1. **HTTP localhost 通信**（不用 stdio JSON-RPC）：复用 DRF 现成
2. **waitress** 跑 Django（不用 runserver dev only）
3. **进程清理**：Electron 关窗 → `taskkill /F /T /PID`（Windows）/ SIGTERM（unix），watchdog 兜底
4. **端口管理**：sidecar 启动时 bind 0（OS 分配），stdout 打印 `listening on port X`，主进程 parse 后注入到 BrowserWindow
5. **dev / prod 双模式**：
   - dev：`npm run dev:electron` → spawn `uv run python sidecar_entry.py`（不打 PyInstaller）
   - prod：spawn `dist/explore-os-sidecar/explore-os-sidecar.exe`
6. **HF_HOME 走 EXPLORE_OS_DATA_DIR/cache**：apps/core/paths 已处理
7. **CUDA 版自用**优先，CPU 版 spec 留 ft-025

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| frontend-shell | ft-023 electron shell + sidecar 启动 + PyInstaller spec | dsp-007 |

## 验收

- `npm run dev:electron` 启 Electron 窗口 + sidecar，window 可访问 `http://127.0.0.1:<port>/api/health/`
- 关窗后 sidecar 进程清理（无残留）
- `npm run build:sidecar` 在用户本机产 PyInstaller bundle（沙箱不验证）
- 既有 Python 测试不破（241+ 全过）
- pyproject.toml 加的 dev-dep 不影响主依赖

## 风险

- **PyInstaller × CUDA torch hidden imports**：torch 动态加载 CUDA DLL 经常被漏；spec 中 hookspath 显式 collect
- **docling 模型路径**：HF_HOME 在 frozen exe 中要走 `_MEIPASS` 之外（已通过 `cache_dir()` 处理）
- **Windows 子进程清理**：`taskkill /F /T /PID` 兜底
- **sidecar 启动慢**（~30s 模型加载）：Electron 主进程 splash + 健康检查轮询

## 里程碑

- W1 D1: package.json + tsconfig + main.ts + BrowserWindow
- W1 D2: sidecar.ts + port.ts + 进程清理 + 健康检查
- W1 D3: sidecar_entry.py + waitress + 联调
- W1 D4: PyInstaller spec + electron-builder yml
- W1 D5: dev / build npm scripts + 文档
- W1 D6-7: buffer

## 每日进展

_(按日追加)_
