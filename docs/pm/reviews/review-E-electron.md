---
review_id: review-E-electron
review_group: E
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---

# Review E — Electron / sidecar / 路径胶水

## 1. 范围确认

**审过的代码（皆已读全文）**：

- Electron shell（5 文件）：`electron/src/main.ts`、`sidecar.ts`、`port.ts`、`preload.ts`、`types.ts`
- Electron 配套：`electron/package.json`、`electron/tsconfig.json`、`electron/build/electron-builder.yml`、`electron/README.md`、`electron/resources/placeholder.html`（仅占位）
- 打包：`build/sidecar-cuda.spec`、`build/hooks/hook-torch.py`
- Sidecar 入口：`sidecar_entry.py`
- 路径胶水：`apps/core/paths.py`、`apps/core/tests_paths.py`、`apps/papers/paths.py`、`config/settings.py`
- 全仓 grep（取证）：`BASE_DIR` / `'media'` / `os.path.join` / `Path(__file__)` / `isPackaged|sys.frozen` / `EXPLORE_OS_DATA_DIR` / `MEDIA_ROOT` / `papers_dir|figures_dir|...` / `app.setName|app.getPath`

**重叠移交**：

- C 组 H10（`extract_paper.py:32` + `interpret_paper.py:32`）已记入 review-C；本报告扩展验证后 **再发现 3 处同类硬编码** + 1 处 docstring/help 文案漂移，全部归 §3 H1。
- B 组：`apps/api/subscriptions_views.py:35` 的 `subscriptions.yaml` 路径硬编码移交 B 组（API 层），但 §3 H4 给出关联说明，因为 frozen 后果一致。

**不在范围**：渲染器/抽取器内部逻辑、Vite 前端、APScheduler、subscriptions YAML schema、CUDA/CPU 双轨 spec 拆分（属 v1.5 ft）。

## 2. 路径硬编码清单（全仓 grep 结果统计）

### 2.1 全仓 `BASE_DIR` 出现统计（剔除 docs/migration/tests 噪音后的运行时引用）

| # | 文件:行 | 形态 | frozen 后果 |
|---|---------|------|-------------|
| 1 | `config/settings.py:9` | `BASE_DIR = Path(__file__).resolve().parent.parent` | 必要（Django 自身需要）；frozen 后是 `_MEIPASS` 临时解压路径 |
| 2 | `config/settings.py:14` | `read_env(BASE_DIR / ".env")` | 读 .env，frozen 后该路径不存在 → 静默 fallback（OK） |
| 3 | `config/settings.py:65` | `TEMPLATES.DIRS = [BASE_DIR / "templates"]` | 只读；PyInstaller 已 datas=("apps","apps") 但 templates 目录 **未显式 datas** — 需复核（不在本组范围，移交打包侧） |
| 4 | `apps/extract/management/commands/extract_paper.py:32` | `Path(settings.BASE_DIR) / "media" / "pdf" / f"{arxiv_id}.pdf"` | **写盘默认路径** → frozen exe 必崩 |
| 5 | `apps/interpret/management/commands/interpret_paper.py:32` | 同上 | 同上 |
| 6 | `apps/extract/figure_extractor.py:40` | `Path(getattr(settings, "BASE_DIR", Path.cwd())) / "media" / "figures"` | **图片落盘** → frozen exe 写不下，且与 `paths.figures_dir()` 不一致（双源 of truth） |
| 7 | `apps/api/subscriptions_views.py:35` | `Path(settings.BASE_DIR) / "subscriptions.yaml"` | 读 yaml；frozen 后是 `_MEIPASS/subscriptions.yaml`（datas 进 asar），用户编辑 yaml 改不到运行时副本 |
| 8 | `apps/papers/brief_generator.py:32` | 同上 `subscriptions.yaml` | 同 #7 |
| 9 | `apps/render/management/commands/render_graph.py:31` | help 文案 `<BASE_DIR>/media/render/<arxiv_id>` | 仅文案（实际默认值用 `render_dir(arxiv_id)`，OK）；文案误导，需改 |

> tests 文件（`apps/extract/tests_docling_ext.py` ×16 处 `settings.BASE_DIR = tmp_path`）属测试桩，不计入。

### 2.2 `media` 字面量

`media` 在运行时代码里出现 5 处运行时引用（除 paths.py 内部 + tests）：均为 §2.1 的 #4–#7。`config/settings.py:18` 的 `MEDIA_ROOT = DATA_DIR / "media"` 是正确锚定（已走 DATA_DIR）。

### 2.3 `os.path.join` / `Path(__file__)`

- `Path(__file__)` 仅 `config/settings.py:9` 一处运行时引用（即 BASE_DIR 自身），健康。
- `os.path.join` 全仓搜索无运行时持久化路径拼接命中（无需改造）。

### 2.4 `explore_os.sqlite3`

3 处运行时引用，**双源** but 一致：
- `config/settings.py:82` 默认 `f"sqlite:///{DATA_DIR / 'explore_os.sqlite3'}"`
- `sidecar_entry.py:88` 强制覆盖 `os.environ["DATABASE_URL"] = f"sqlite:///{Path(args.data_dir) / 'explore_os.sqlite3'}"`
- 评估：sidecar 强制覆盖是为了打掉 dev `.env` 的 `DATABASE_URL` 漏入桌面端（dsp-008 决策正确，docstring 已说明）。**不算 hotspot**。

### 2.5 dev/frozen 分支

- `electron/src/sidecar.ts:47` 唯一 `app.isPackaged` 分支。Python 侧 **零** `getattr(sys, 'frozen', False)`／`sys._MEIPASS` 引用。这是优点（路径走 DATA_DIR，dev/frozen 同源），但也意味着 §2.1 #3 / #7 / #8 这类靠 `BASE_DIR` 读静态资产的位置在 frozen 下行为微妙——见 §3 H4。

## 3. 耦合 hotspot（最多 15 条）

| # | hotspot | 文件:行 | 严重度 | 阻塞 v1.5 |
|---|---------|---------|--------|-----------|
| H1 | **`BASE_DIR/media/...` 写盘四宗罪** —— `extract_paper.py:32`、`interpret_paper.py:32`、`figure_extractor.py:40`，外加 `render_graph.py:31` 的 help 文案。frozen exe 的 `BASE_DIR=_MEIPASS` 只读，命令行落盘必崩；管理命令是用户/调度器主入口 | `apps/extract/management/commands/extract_paper.py:32`、`apps/interpret/management/commands/interpret_paper.py:32`、`apps/extract/figure_extractor.py:40`、`apps/render/management/commands/render_graph.py:31` | 3 | **yes** |
| H2 | **`figure_extractor` 双源 of truth** —— `figure_extractor.py:40` 自己拼 `BASE_DIR/media/figures`，绕过 `apps.papers.paths.figures_dir()`。dev 巧合落到 repo `media/`、frozen 落到 `_MEIPASS/media/`，**与 `paths.figures_dir()` 返回的 `DATA_DIR/media/figures` 不一致**——同一 arxiv_id 在两个目录都可能产物，下游 figure_picker 找不到图 | `apps/extract/figure_extractor.py:40` | 2 | yes（行为分裂） |
| H3 | **`subscriptions.yaml` 静态读路径** —— `subscriptions_views.py:35` + `brief_generator.py:32` 都从 `BASE_DIR/subscriptions.yaml` 读。frozen 后该文件随 `datas=("apps","apps")` 同级被打入 `_MEIPASS`（且 spec 未显式 datas yaml，可能根本不进 bundle），用户在 DATA_DIR 编辑 yaml 改不到运行时副本 | `apps/api/subscriptions_views.py:35`、`apps/papers/brief_generator.py:32` | 3 | **yes** |
| H4 | **`templates/` 目录未声明 datas** —— `settings.py:65` 的 `TEMPLATES.DIRS = [BASE_DIR / "templates"]` 在 frozen 下指向 `_MEIPASS/templates`，但 `build/sidecar-cuda.spec` 的 datas 只列 `("apps","apps")`，仓库根 `templates/` 目录（若存在）需显式加入；任何 Django 模板渲染（含 admin）会 TemplateDoesNotExist | `build/sidecar-cuda.spec` datas + `config/settings.py:65` | 2 | 取决于是否有运行时模板（admin / email html）；保守 yes |
| H5 | **`app.setName` 时机正确，但靠 `app.getPath('userData')` 单点传 DATA_DIR** —— `main.ts:105` 的 `app.setName('explore-os')` 在 `app.requestSingleInstanceLock` 与 `app.whenReady` 之前，时机 OK；但 `sidecar.ts:46` 用 `app.getPath('userData')` 派生 `--data-dir`，**未给用户/CLI override 钩子**（开发者无法不改代码切到自定义目录跑 sidecar；运维诊断不便） | `electron/src/main.ts:105`、`electron/src/sidecar.ts:46` | 1 | no（功能可用，UX/可调试性问题） |
| H6 | **端口管理：sidecar 单例靠 `proc != null`，无锁文件 / 无端口持久化** —— `sidecar.ts:41` 仅以模块级变量 `proc` 判重，依赖 Electron `requestSingleInstanceLock` 兜底多 Electron 实例；若锁文件机制失败（不同 userData 路径、locker 存在但 process 死），第二个 Electron 会再 spawn 一个 sidecar 抢端口（虽然 `--port 0` 不冲突），但两份 Django 同写 SQLite → WAL 锁竞争 | `electron/src/sidecar.ts:28`、`electron/src/main.ts:108` | 2 | no（多实例边角；单实例 happy path OK） |
| H7 | **sidecar spawn env 仅注入 `PYTHONUNBUFFERED`，DATA_DIR 走 CLI argv** —— `sidecar.ts:94` 的 `env: { ...process.env, PYTHONUNBUFFERED: "1" }` 不显式设 `EXPLORE_OS_DATA_DIR`；sidecar_entry.py:80 接到 `--data-dir` 后才 `os.environ["EXPLORE_OS_DATA_DIR"] = args.data_dir`。两条路径达成同样效果，但若用户在父 shell 设了 `EXPLORE_OS_DATA_DIR`，**会被 sidecar_entry 内部 `args.data_dir`（来自 Electron userData）覆盖**——文档/直觉与行为相反 | `electron/src/sidecar.ts:94`、`sidecar_entry.py:80` | 1 | no（一致性 / 文档问题） |
| H8 | **stdout banner 解析单点失败** —— `port.ts:14` 的 `LISTENING_RE = /\[sidecar\]\s+listening on\s+https?:\/\/[^:\s]+:(\d+)/i` 是端口握手唯一通道。若 PyInstaller 启动期 stderr 抢先吞了 banner（已尝试 stderr fallback：`sidecar.ts:193`，OK），或 sidecar_entry 改了文案，整套启动 30s 后 timeout。**强约束没有断言测试** | `electron/src/port.ts:14`、`sidecar_entry.py`（banner 字面量） | 2 | no（脆弱但当前能跑） |
| H9 | **`BASE_DIR/.env` 在 frozen 下静默 fallback** —— `settings.py:14` `read_env(BASE_DIR / ".env")` frozen 后该路径不存在；目前 sidecar_entry.py 的 `os.environ` 显式覆盖兜底了关键变量（`DATABASE_URL`、`EXPLORE_OS_DATA_DIR`），但**任何后续新增 .env 变量（如 LLM API key）会在 frozen 下默默缺失**——属"成功的 footgun" | `config/settings.py:14`、`sidecar_entry.py:80-93` | 2 | 取决于是否新增依赖 .env 的 secret；中期 yes |

## 4. dev/frozen 分支对称性

**单点分支位置**：`electron/src/sidecar.ts:47` 的 `const isDev = !app.isPackaged;`，分支体仅决定 `cmd / args / cwd / shell` 四个 spawn 参数。Python 侧零 `sys.frozen` / `sys._MEIPASS` 引用，sidecar_entry.py 与 Django apps 全部走 `EXPLORE_OS_DATA_DIR`（v0.9 ft-022 落地）→ paths.py 抽象层 → `app.getPath('userData')`。

**评估**：

- ✅ **优点**：dev 与 frozen 在 Python 侧走同一份数据路径解析逻辑，`apps/core/paths.py` 是唯一抽象层；这是 ft-022 的核心成果，避免了 dual-codepath 的认知负担。理论上 dev 验过的逻辑 frozen 应自动可用。
- ⚠️ **风险**：dev/frozen 同源的前提是**所有写盘点都通过 paths.py**。§3 H1+H2+H3 揭示该前提被 4-6 处硬编码打破——这些点 dev 巧合能跑（repo 工作树可写），frozen 必崩。**没有 CI 检测这一类回归**：当前 `tests_paths.py` 只测 paths.py 自身，不扫管理命令是否绕开它。
- ⚠️ **二级风险**：`BASE_DIR` 在 frozen 下指向 `_MEIPASS`（PyInstaller 临时解压目录），**不是不可变错误而是只读 + 易消失**；任何依赖 `BASE_DIR/...` 读静态资产的代码（templates、subscriptions.yaml）必须在 spec datas 显式列出，否则 silently 缺。
- ✅ **dev/prod 的 cwd 对齐**：dev `cwd = projectRoot`（two dirs up from `dist-electron`），frozen `cwd = undefined`（PyInstaller bootloader 自管）；Django settings 不再使用 `os.getcwd()`，所以 cwd 差异无害。
- ❌ **缺单元测试**：`port.ts` 的 banner 正则、`sidecar.ts` 的 `isDev` 分支、`waitForListeningLine` 的 stderr fallback 都无测试。frozen 路径只能靠端到端验。建议至少给 `parseListeningLine` 加单测（4 行就能覆盖正例 + 大小写 + http/https + 反例）。

**结论**：单点分支是**优点**（架构干净），但前提依赖路径抽象层无泄漏；当前 hotspot H1-H4 是该假设的违反。修完 H1-H4 后，dev/frozen 对称性就稳固了。

## 5. sidecar 启动 / 端口管理评估

**启动链路**（`main.ts → sidecar.ts → port.ts → sidecar_entry.py`）：

1. `main.ts:105` `app.setName('explore-os')` — 早于 `requestSingleInstanceLock` 与 `whenReady`，时机正确，确保 `app.getPath('userData')` 落到 `%APPDATA%/explore-os/`。
2. `main.ts:108` `app.requestSingleInstanceLock()` — 第二实例直接 `app.quit()`，并通过 `second-instance` 事件聚焦既有窗口。**未防多 userData 路径的多实例**（不同 `--user-data-dir` 启动会绕过锁），但属 Electron 通用限制，可接受。
3. `app.whenReady → bootstrap → startSidecar → createWindow` 串行：sidecar 起不来则 `dialog.showErrorBox + app.exit(1)`，**不会出现"窗口起来 sidecar 没起"的半残状态**——这是好的。
4. `sidecar.ts:46` `dataDir = app.getPath('userData')` —— 单一来源，与 settings.py 解析路径一致（间接通过 `--data-dir` arg → sidecar_entry.py:80 `os.environ["EXPLORE_OS_DATA_DIR"]`）。
5. `sidecar.ts:53-90` dev/frozen 分支：dev 优先用 `.venv/Scripts/python.exe` 直接跑，避免 `uv run` 在受限网络（SOCKS proxy）下尝试同步 CUDA torch mirror 卡死——这是踩过坑的修复，注释完整，赞。`shell: isDev && win32` 仅在 `cmd === "uv"` 兜底分支需要 PATH 解析时启用，frozen 走绝对路径不开 shell（防 quoting 问题），合理。
6. `sidecar.ts:92` `spawn(cmd, args, { env: { ...process.env, PYTHONUNBUFFERED: "1" }, ... })` —— `windowsHide: true` 防黑窗，`stdio: ["ignore", "pipe", "pipe"]` 让父进程能解析 banner。**未传显式 `EXPLORE_OS_DATA_DIR` env**（依赖 `--data-dir` argv → entry 内部设环境变量）；H7 已述。
7. `port.ts:14` 正则 `\[sidecar\]\s+listening on\s+https?:\/\/[^:\s]+:(\d+)` 解析 banner；`sidecar.ts:193` 的 stderr fallback 涵盖 PyInstaller 把 stdout 缓冲到 stderr 的少见情况。banner 文案是 sidecar Python 与 Electron 的隐式契约，**两侧无共享常量**——若改文案双边必须同步改，建议挪到 `electron/src/types.ts` 或写 `sidecar.ts` 顶部常量加注释。
8. `port.ts:29` `waitForHealth` 30s 轮询 `/api/health/`，500ms 间隔，每次 2s 超时。30s 是 Django boot + 首次 migrate 的预算，frozen 下首启动可能更慢（`_MEIPASS` 解压 + docling 模型按需加载）；建议 frozen 分支把 timeout 拉到 60s。
9. `sidecar.ts:103` `child.on('exit')` 仅更新 `info.status`，**未触发自动重启**——崩溃后需要用户手动重启 Electron。当前 MVP 阶段可接受；v1.x 可加重试预算（exponential backoff，最多 3 次）。
10. `sidecar.ts:137` Windows 下 `taskkill /F /T /PID` 处理 PyInstaller bootloader → 子进程双层结构，覆盖到位。Unix `SIGTERM → 5s grace → SIGKILL` 标准做法。

**端口选择**：`--port 0` 让 OS 选——避免 TOCTOU race，正确。但 sidecar 选到的端口**只活在内存里**，IPC `explore:get-backend-port` 返回；前端通过 preload 拿到后调用 `http://127.0.0.1:<port>`。**未持久化端口**——任何外部观测/调试（curl 验接口）需先看 Electron 日志，UX 偏弱。可考虑把 port 写到 `userData/sidecar.port` 给开发者读。

**整体评分**：架构合理，关键决策（`--port 0`、`taskkill /T`、early `setName`、dev venv 优先、boot 串行）都踩过坑后修对。主要欠缺：(a) 启动失败无重试，(b) banner 文案契约无共享常量，(c) frozen timeout 偏紧。

## 6. 解耦改造提议（最多 10 条）

| # | 提议 | 关联 hotspot | 工作量 | 优先级 |
|---|------|-------------|--------|--------|
| P1 | **统一 `BASE_DIR/media` 写盘** —— 把 4 处 `Path(settings.BASE_DIR) / "media" / ...` 全部改走 `apps.papers.paths.papers_dir(arxiv_id)` / `figures_dir(arxiv_id)` / `pdf_path(arxiv_id)`。`figure_extractor.py:40` 把 `getattr(settings, "BASE_DIR", Path.cwd())` fallback 一并删掉（`paths.figures_dir()` 已用 `EXPLORE_OS_DATA_DIR`） | H1, H2 | S（4 文件改 import + 拼路径行，~30 行） | **P0**（v1.5 必修） |
| P2 | **`subscriptions.yaml` 走 DATA_DIR + 默认副本机制** —— 在 `apps/core/paths.py` 新增 `subscriptions_yaml_path()`（`DATA_DIR / "subscriptions.yaml"`）；`subscriptions_views.py` + `brief_generator.py` 改用之。frozen 首次启动检测 DATA_DIR 无 yaml 则从 `_MEIPASS/apps/.../default_subscriptions.yaml` 复制兜底。spec 把默认 yaml 列入 datas | H3 | M（2 文件 + paths 增 1 函数 + spec 调整 + 首启动 seed 逻辑） | **P0** |
| P3 | **`templates/` datas 显式声明** —— 复核 `build/sidecar-cuda.spec` 的 `datas`，若仓库根有 `templates/` 加 `("templates", "templates")`；同时给 `apps/*/templates/` 的子模板做 `collect_data_files('apps')` 的 verify 测试（启动 sidecar 后 GET admin login 不应 TemplateDoesNotExist） | H4 | S | P1 |
| P4 | **banner 契约共享常量化** —— 在 sidecar Python 与 Electron `port.ts` 之间确立单一文案源；最简：`sidecar_entry.py` 顶部 `LISTENING_BANNER = "[sidecar] listening on http://{host}:{port}"`，`port.ts` 注释引用该字面量来源。中期可让 sidecar 把端口写到 `userData/sidecar.port` 文件（持久化 + 减弱 banner 解析依赖） | H8 | XS（单常量 + 注释） | P2 |
| P5 | **EXPLORE_OS_DATA_DIR override 钩子** —— `sidecar.ts:46` 改成 `process.env.EXPLORE_OS_DATA_DIR ?? app.getPath('userData')`，让开发者/CI/运维能不改代码切目录。同步在 `sidecar.ts` env 显式注入 `EXPLORE_OS_DATA_DIR: dataDir`，与 `--data-dir` argv 双保险（H7 文档/直觉对齐） | H5, H7 | XS（3 行） | P1 |
| P6 | **frozen 启动 timeout 分支** —— `HEALTH_TIMEOUT_MS = isDev ? 30_000 : 60_000`（首次启动 PyInstaller `_MEIPASS` 解压 + docling 模型加载 + Django migrate 在冷盘 / 杀软扫描下能跑到 40s+） | §5 #8 | XS | P1 |
| P7 | **CI 路径硬编码守卫** —— 加一个 `apps/core/tests_paths_lint.py`：grep `apps/**/*.py` 不应出现 `BASE_DIR / "media"` 或 `BASE_DIR / "subscriptions"` 字面量（除 `paths.py` / settings.py 白名单）；防止 ft-022 类回归再次发生 | H1, H2, H3 | S（一个 pytest，AST 或纯 grep 都行） | P1 |
| P8 | **sidecar 异常重启策略** —— `sidecar.ts` 加 `MAX_RESTART = 3` + 指数退避；`child.on('exit')` 非 stopping 状态触发重启而非直接 error。给前端发 `explore:sidecar-restarting` 事件 | §5 #9 | M | P2（v1.x，非 v1.5 必需） |

## 7. 不在范围 / 移交其它 group

- **C 组（抽取/解读 pipeline）**：H1 中 `extract_paper.py:32` + `interpret_paper.py:32` 两处与 review-C 的 H10 重叠，由 C 组主导修复（涉及命令行 default 语义）；本组 P1 已包含同一改造范围，建议 C/E 合并到一个 ft 落地，避免双 PR 冲突。
- **B 组（API 层 / subscriptions 配置）**：H3 的 `subscriptions_views.py:35` 属 API 层，移交 B 组；`brief_generator.py:32` 属 papers app 但读同一文件，建议两处一起改，归 B 组主导 + papers 协作。
- **打包侧（v1.5 ft-026 / 双轨 spec 拆分）**：H4 的 `templates/` datas、P2 的 default_subscriptions.yaml seed、P3 的 spec 改造，全部归打包侧 ft；review-E 在 §3 标出 hotspot，具体方案由打包 ft 负责。
- **不审**：APScheduler 调度（review-D 范围）、Vite 前端（review-F? 未在本轮）、subscriptions YAML schema（review-B 范围）、CUDA/CPU 双轨 spec 拆分（v1.5 ft 设计）。
- **后续验证 hook**：P7 的 CI 路径硬编码守卫建议在 review 收尾后由 PM 拍板加入 iter-019 的 wrap-up，作为本轮 review 的 enforcement 抓手。
