# explore-os 单机 app packaging 调研（ft-022）

> 本文档为 v1.0「explore-os 桌面单机 app」的 **选型 + 可行性决策** 调研，**不动业务代码**。
> Owner: dsp-002 / ft-022
> Created: 2026-04-25
> Status: research
>
> 主结论提前：**Tauri 2.x + PyInstaller sidecar (Django) + SQLite + APScheduler in-process**
> 是当前最契合 explore-os 架构的路径。Electron 作为兜底（切换成本极低）。
> 现有代码层面**对单机化几乎零阻碍**：models.py 全为空（数据持久化在 `media/**` 文件系统），
> 没有 `ArrayField` / `tsvector` / 原生 SQL；唯一硬约束是 SMTP 必填 + LLM API 在线。

---

## 1. Tauri 路径

### 1.1 架构总览

```
+----------------------------------------------------------+
| Tauri Shell (Rust + WebView, ~10MB)                      |
|   ┌─────────────────────────────────────────────────┐    |
|   │  Frontend (Vite + React/Svelte/Vanilla)         │    |
|   │   ── fetch("http://127.0.0.1:<port>/api/...")  ─┼──┐ |
|   └─────────────────────────────────────────────────┘  │ |
|                                                         │ |
|   spawn sidecar  ─────────►  python-<triple>.exe        │ |
|                              (PyInstaller bundle)       │ |
|                              └── Django (manage.py      │ |
|                                  runserver --noreload)  │ |
|                                  ↳ SQLite (appData)  ◄──┘ |
|                                  ↳ media/ (appData)        |
+----------------------------------------------------------+
```

### 1.2 Sidecar 启动 Python 的方式

| 通信 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| **HTTP localhost:<random_port>** | Django/DRF 现成；前端用标准 fetch；与项目当前 REST API 形态一致 | 占用本地端口；防火墙/杀软可能拦截；端口冲突需重试 | ✅ **推荐** |
| stdio (JSON-RPC over pipes) | 无端口；无防火墙问题；强进程绑定 | Django 不天然支持；需要单写一层 RPC 调度；REST 现有路由全废 | ❌ 跳出 Django 生态成本太高 |
| Unix socket / Named pipe | 无端口、无防火墙 | Windows / macOS / Linux 三套实现；Django 需 wrapper | ❌ 收益不抵成本 |

**实施要点（HTTP 方案）**：

1. Tauri Rust 端用 `tauri_plugin_shell::ShellExt::sidecar(...).spawn()` 启 sidecar，监听其 stdout 抓「listening on port」字符串拿到端口（或固定一个先 bind 试错）。
2. Sidecar 入口建议**不用** `manage.py runserver`（dev only），改用 `waitress-serve --listen=127.0.0.1:0 config.wsgi:application`（Windows/Linux）或 `gunicorn`（macOS/Linux）。需新增 `waitress` 依赖（**不在本 ft 范围**，packaging ft 阶段再加）。
3. Tauri 在窗口 `close-requested` 事件里向 sidecar 发 SIGTERM；并启 watchdog 用 `psutil` 检查 parent PID 是否还在，若不在则 self-terminate（社区已知 sidecar 残留进程问题，[tauri-apps#2759](https://github.com/tauri-apps/tauri/discussions/2759)）。
4. 前端 baseURL 通过 Tauri `invoke('get_backend_port')` 获取后注入。

### 1.3 PyInstaller 打包 Django 的实操要点

已知坑（来自 [PyInstaller 6.x docs](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) + Django wiki）：

| 坑 | 触发 | 解决 |
|----|------|------|
| **Django auto-reload** | `runserver` 默认 fork 子进程 watch 文件，frozen exe 不允许 | 用 `--noreload` 或换 waitress/gunicorn |
| **App autodiscover 丢失** | `INSTALLED_APPS` 里的 app 模块 PyInstaller 静态分析看不到 | spec 文件 `hiddenimports=['subscriptions','sources','interpret','delivery','rest_framework',...]` 全列；或在 manage.py 顶部加显式 `import` |
| **Template loader / app_dirs** | `APP_DIRS=True` 时 Django 走文件系统 walk 查模板，frozen 后路径不在 | `datas=[*collect_data_files('rest_framework'),*collect_data_files('django.contrib.admin'),('templates','templates')]` |
| **Static files (admin/DRF)** | 同上，`/static/admin/...` 404 | `collectstatic` 到 `STATIC_ROOT`，PyInstaller `datas` 把 `STATIC_ROOT` 整目录打进去；运行时 `whitenoise` 服务静态文件 |
| **Migrations 找不到** | Django `find_commands` 扫 `*.py` 目录，one-file 模式没文件 | hook 强制 `collect_submodules('subscriptions.migrations')` 等四个 app；或 `--onedir`（推荐，便于排错） |
| **manage.py find_commands** | 自定义命令（`run_subscription`、`adhoc_fetch`）扫 `management/commands/*.py` 失效 | 显式 hiddenimports 列出每个 command module；或 monkey-patch `django.core.management.find_commands` |
| **psycopg / pymupdf 二进制** | 二进制 wheel 的 .so/.dll 漏带 | PyInstaller 通常自动收齐；切到 SQLite 后 psycopg 可移除（见 §3） |
| **pymupdf 资源文件** | mupdf 自带字体/CMap | `collect_data_files('pymupdf')` |

**spec 文件骨架**（参考，不在本 ft 实施）：

```python
# explore_os.spec
a = Analysis(
    ['manage.py'],
    pathex=['.'],
    hiddenimports=[
        'subscriptions', 'subscriptions.apps',
        'subscriptions.management.commands.run_subscription',
        'sources', 'sources.apps', 'sources.fetchers.arxiv', 'sources.fetchers.hf_papers',
        'sources.management.commands.adhoc_fetch',
        'interpret', 'interpret.apps',
        'delivery', 'delivery.apps',
        'delivery.adapters.email', 'delivery.adapters.feishu', 'delivery.adapters.wechat_subscription',
        'rest_framework', 'django.contrib.admin', 'django.contrib.auth',
        'django.contrib.contenttypes', 'django.contrib.sessions',
        'django.contrib.messages', 'django.contrib.staticfiles',
        'whitenoise',  # 新增：静态文件服务
        'waitress',    # 新增：WSGI server
    ],
    datas=[
        *collect_data_files('rest_framework'),
        *collect_data_files('django.contrib.admin'),
        *collect_data_files('django.contrib.auth'),
        *collect_data_files('pymupdf'),
        ('templates', 'templates'),  # 项目 templates/
        ('staticfiles', 'staticfiles'),  # collectstatic 输出
    ],
)
```

### 1.4 包体大小预估

| 组件 | 大小 |
|------|------|
| Tauri Rust 壳 + WebView2 (Win 复用系统) | ~10 MB |
| Tauri 壳 + 自带 WebView (macOS WKWebView 系统/Linux WebKitGTK) | ~10–25 MB |
| PyInstaller --onedir Django bundle | **80–150 MB** |
|   ├─ Python 3.12 runtime | ~25 MB |
|   ├─ Django + DRF + django-environ + waitress + whitenoise | ~20 MB |
|   ├─ pymupdf + pymupdf4llm（含 mupdf 二进制 + 字体） | ~50–80 MB ⚠️ |
|   ├─ httpx + tenacity + pyyaml + pydantic | ~10 MB |
|   └─ 不再含 psycopg（切 SQLite 后省 ~15 MB） | -15 MB |
| 前端（Vite 产物，假设 React + 几十个组件） | 1–3 MB |
| **总安装包 (.msi / .dmg / .AppImage)** | **~100–180 MB** |

> **关键变量**：`pymupdf` 是体积最大头。若 v1.0 决定继续在客户端做 PDF chunk + figure 渲染，包体就跑不掉。
> 替代方案（不在本 ft 范围）：把 PDF 处理拆为可选远程 service，但这又违反单机假设——**不建议拆**。

### 1.5 跨平台构建流程

| 平台 | 构建产物 | 关键命令链 | 已知坑 |
|------|---------|-----------|--------|
| Windows x64 | `.msi` (WiX) / `.exe` (NSIS) | `pyinstaller explore_os.spec` → 产物移到 `src-tauri/binaries/explore-os-x86_64-pc-windows-msvc.exe` → `tauri build` | Windows Defender 假阳（[#2486](https://github.com/tauri-apps/tauri/issues/2486)、[#10649](https://github.com/tauri-apps/tauri/issues/10649)）→ 必须 **代码签名证书**（EV cert ~$300/年）才能去黄字告警；MSI 安装路径权限问题 |
| macOS (Intel + Apple Silicon) | `.dmg` / `.app` | 双架构需各跑一次 PyInstaller（不能 cross-build），或用 `lipo` 合并 universal2 | **必须公证（notarization）**，需 Apple Developer ID（$99/年）；首次启动 Gatekeeper 警告 |
| Linux x64 | `.AppImage` / `.deb` | 单 PyInstaller bundle 即可；建议在最老 supported glibc（Ubuntu 20.04）构建以提高兼容性 | WebKitGTK 版本差异；不同发行版 SSL 证书路径 |

**CI/CD 推荐**：GitHub Actions 三个 runner（windows-latest / macos-latest / ubuntu-22.04），各自 PyInstaller + Tauri build，artifact 上传 release。

### 1.6 已知 sidecar 失败模式 + 缓解

| 失败模式 | 触发 | 缓解 |
|---------|------|------|
| Sidecar 启动失败（Python 路径错） | one-file 模式 `_MEIPASS` 临时解压目录权限/AV 拦 | 用 `--onedir`，路径稳定 |
| 端口被占 | 用户已开同名服务或被其他进程抢 | 让 sidecar 启时绑定 port=0 → 拿到 OS 分配端口 → 写到 stdout 一行 `EXPLORE_OS_PORT=<n>`，Rust 端读 |
| 关 app 后 Python 残留 | Tauri 的 `close-requested` 没等 sidecar exit | sidecar 内 watchdog 线程：每 5s 检查 parent PID（环境变量传入）；不在则 `os._exit(0)` |
| 防火墙/杀软拦截 | 首次启动弹「允许 explore-os 访问网络」；Kaspersky/360 直接杀 | 仅监听 `127.0.0.1`（不是 `0.0.0.0`）通常可避；签名 + 上 Microsoft SmartScreen 提交 reputation；准备 FAQ |
| Migration 失败 | 用户 home 目录无写权限 / SQLite 数据库被锁 | 启动时 try `migrate`，捕获后弹原生 dialog 提示（Tauri `dialog` plugin） |
| LLM API key 未配置 | 现网 LLM 调用 `LLMError("LLM_API_KEY is not configured")` | 首次启动 onboarding 引导用户填 API key；存到 OS keyring（Tauri `tauri-plugin-stronghold` 或前端走 `keytar`） |

---

## 2. Electron 兜底

### 2.1 成熟方案

`electron-builder` + PyInstaller sidecar 是 Electron 生态的标准套路（[electron-python-example](https://github.com/fyears/electron-python-example) 维持十年活跃）：

```jsonc
// package.json
"build": {
  "extraResources": [
    { "from": "py_dist/", "to": "py_dist/", "filter": ["**/*"] }
  ]
}
```

主进程 `child_process.spawn(path.join(process.resourcesPath, 'py_dist', 'explore-os'), [...])`，渲染进程通过 IPC 拿端口。

### 2.2 包体差距

| 项 | Tauri | Electron |
|----|-------|----------|
| 壳 | 10 MB | **~80–120 MB**（含 Chromium + Node） |
| Python sidecar | ~80–150 MB | ~80–150 MB（一致） |
| **总安装包** | ~100–180 MB | **~180–270 MB** |

差 ~80 MB 主要在 Chromium。对桌面 app 而言不致命。

### 2.3 Tauri → Electron 切换成本

**前端用标准 Web 技术**（Vite + React/Vanilla + fetch）则迁移成本低：

- Tauri-specific：`@tauri-apps/api` 的 `invoke` / `dialog` / `shell` / `fs` 调用 → 替换为 Electron `ipcRenderer` / `dialog` / `shell` / `fs`（一一对应，纯改 import + 函数名）
- IPC 协议层：写一个 `bridge.ts` 抽象层，里面分支 `if (window.__TAURI__) ... else if (window.electronAPI) ...`，从 day 1 就这么做
- Sidecar spawn 逻辑 100% 复用 PyInstaller 产物，只换宿主进程
- 估计切换工作量：**1–2 人日**（前提：前端层有 bridge 抽象）

> **设计准则**：v1.0 前端写代码时**禁止直接 import `@tauri-apps/api`**，必须经 `bridge.ts`。这是阻止 Tauri 锁定的最便宜保险。

---

## 3. SQLite 切换扫描（实际代码扫描结果）

### 3.1 关键发现：models.py 全部为空

扫描结果（grep 全 zero hit）：

| 检查项 | 结果 |
|--------|------|
| `ArrayField` / `HStoreField` / `tsvector` / `SearchVector` / `GinIndex` / `contrib.postgres` | **0 处** |
| `RunSQL` / `raw_sql` / `objects.raw(` | **0 处** |
| `update_or_create` / `bulk_create` / `get_or_create` / `select_for_update` | **0 处** |
| 各 app `migrations/` 目录除 `__init__.py` | **空** |
| `apps/*/models.py` 实际行数 | `subscriptions/models.py`、`sources/models.py`、`interpret/models.py`、`delivery/models.py` **均为 1 行（空文件）** |

**结论**：当前数据持久化**完全不走 ORM**，全部走 `media/` 文件系统：

- 订阅状态 → `subscriptions.yaml`（文件，`subscriptions/loader.py:42` `yaml.safe_load`）
- 推送历史 / 解读缓存 / 记忆线 → `media/memory/<sub_name>/{runs.jsonl, papers.jsonl, digests.md}`（`subscriptions/memory.py`）
- PDF 缓存 → `media/papers/<arxiv_id>.pdf`（`sources/pdf_fetcher.py:29`）
- 图缓存 → `media/figures/<arxiv_id>/*.png`（`interpret/figure_extractor.py`）

Django ORM 当前只为系统 app（admin/auth/sessions/contenttypes）服务，**这些原生支持 SQLite**。

### 3.2 切换 patch 清单（文件 + 行号 + 改动方向）

> 以下 **不修改**，仅记录后续 packaging ft 实施清单。

| # | 文件 | 行号 | 现状 | 改动方向 |
|---|------|------|------|---------|
| 1 | `config/settings.py` | 60–65 | `DATABASES = {"default": env.db("DATABASE_URL", default="postgres://explore:explore@localhost:5432/explore_os")}` | 改为：默认 SQLite 落到 `appdirs.user_data_dir('explore-os') / 'explore_os.sqlite3'`；保留 `DATABASE_URL` env 覆盖（开发/CI 仍可指 PG） |
| 2 | `pyproject.toml` | 11 | `"psycopg[binary]>=3.2"` | 移到可选 group `[dependency-groups] pg = [...]`；不打进 PyInstaller bundle |
| 3 | `pyproject.toml` | 7–18 | 缺 `whitenoise` / `waitress` | 新增：`whitenoise>=6.7`（静态）、`waitress>=3.0`（WSGI server，跨平台） |
| 4 | `docker-compose.yml` | 全文 | 仅 PG 服务，单机版无意义 | 标注「dev only」；packaging 时不打进 release |
| 5 | `subscriptions/memory.py` | 22 | `Path(getattr(settings, "BASE_DIR", Path.cwd())) / "media" / "memory"` | 改为：从 settings 读 `EXPLORE_OS_DATA_DIR`，默认 `appdirs.user_data_dir(...)`；现 `BASE_DIR` 在 frozen exe 中是临时解压目录，会丢失数据 |
| 6 | `sources/pdf_fetcher.py` | 29 | 同上 `BASE_DIR / "media" / "papers"` | 同上：走 `EXPLORE_OS_DATA_DIR / "papers"` |
| 7 | `interpret/figure_extractor.py` | （未读，待 packaging ft 扫描） | 推测同样使用 `BASE_DIR / "media" / ...` | 同上 |
| 8 | `subscriptions/loader.py` | 42 | `Path(path).read_text(...)` 默认指 `subscriptions.yaml`（CWD 相对） | 默认改为 `EXPLORE_OS_CONFIG_DIR / "subscriptions.yaml"`；首次启动若不存在则从 bundle 内的 `subscriptions.example.yaml` 拷贝 |
| 9 | `config/settings.py` | 87–95 | SMTP 配置必填才能投递 | 见 §7 耦合点 |
| 10 | （所有 commands） | — | `BASE_DIR / "media" / ...` 模式 | 全局替换为 `settings.EXPLORE_OS_DATA_DIR` |

**ORM 层结论**：因为没有自定义 model + 没有 PG-only 字段，Django 的 `migrate` 会无障碍生成 SQLite schema（仅系统表）。**ORM 0 行 patch**。

### 3.3 数据迁移（首次启动）

不需要数据迁移——所有用户态数据本来就是文件，PG 切 SQLite 不影响：

1. 首次启动 `migrate` 建系统表
2. `subscriptions.yaml` 不存在则从 bundle 拷贝模板
3. `media/` 目录按需 `mkdir(parents=True, exist_ok=True)`（现有代码已这么写）

---

## 4. 桌面端调度器

### 4.1 选型对比

| 方案 | 依赖 | 进程模型 | 适配桌面 |
|------|------|---------|---------|
| **APScheduler** in-process | 0 外部依赖（纯 Python） | 跑在 Django sidecar 同进程内（`BackgroundScheduler`） | ✅ **推荐** |
| Django-Q2 | DB（OK） / Redis（不行） | DB-broker 模式可，但需独立 worker 进程 | ⚠️ DB-only 模式可用，但相对 APScheduler 复杂度高 |
| Celery + Redis | Redis 服务 | 三进程（broker / worker / beat） | ❌ 桌面用户跑 Redis 不现实 |
| 系统 cron / Task Scheduler | OS 服务 | 跨平台不一致；用户得装 explore-os CLI | ❌ 体验割裂 |

### 4.2 APScheduler 集成方案

```python
# apps.py 或专门的 scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

def boot():
    for sub in load_all_subscriptions():
        for d in sub.deliveries:
            if d.schedule:  # cron 串
                scheduler.add_job(
                    run_subscription_job,
                    CronTrigger.from_crontab(d.schedule),
                    args=[sub.name],
                    id=f"{sub.name}:{d.channel}",
                    replace_existing=True,
                )
    scheduler.start()
```

入口在 Django `AppConfig.ready()` 触发；frozen 后 `--noreload` 保证只启一次。

### 4.3 「立即抓取」按钮设计

前端 → `POST /api/runs/`（DRF 视图）→ `subprocess` 调 `python -m django run_subscription <name>` 或直接 in-process `call_command("run_subscription", ...)` 把当前请求挂在 BackgroundScheduler 的 `add_job(..., next_run_time=now)` 上。

**推荐 in-process** + 异步：DRF 视图返回 `run_id`，前端轮询 `/api/runs/<id>/status` 看进度。需要轻量 run-state 持久化，可写到 `media/runs/<id>.json`（沿用文件路线）。

---

## 5. 风险清单

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | **Windows Defender / 360 / Kaspersky 假阳** | 用户首次启动看到 trojan 警告，劝退 | 上 EV 代码签名证书；提交 Microsoft SmartScreen / 主流 AV 白名单 reputation；FAQ 文档说明 |
| R2 | **Python runtime + pymupdf 体积 ~100MB** | 安装包 > Tauri 「轻量」承诺；下载时间长 | onedir 模式 + delta-update（Tauri updater 支持）；默认下载页选「核心包 50MB（不含 PDF 图渲染）」 + 「完整包 180MB」 |
| R3 | **macOS notarization** | 不公证则 Gatekeeper 直接拒；公证需 Apple Developer 账号（$99/年） | 必须做；CI 内嵌 `xcrun notarytool` 流程 |
| R4 | **跨架构 macOS** | Intel + Apple Silicon 两份产物；PyInstaller 不能 cross-build | universal2 用 `lipo` 合并，或 release 两份 dmg |
| R5 | **localhost 端口冲突** | 用户跑了别的开发服务占了固定端口 | 端口 0 让 OS 分配；不预设固定端口 |
| R6 | **自动更新** | 桌面 app 必须能升级 | Tauri updater 内置（签名 + manifest.json 静态托管 GitHub Releases） |
| R7 | **用户数据目录跨平台** | `BASE_DIR / "media"` 在 frozen 后不可写 | 用 [`appdirs.user_data_dir`](https://pypi.org/project/appdirs/)：Win `%APPDATA%/explore-os/`、macOS `~/Library/Application Support/explore-os/`、Linux `~/.local/share/explore-os/` |
| R8 | **API key 安全** | LLM_API_KEY 落在 .env 文本明文，单机 app 不能这么干 | 存 OS keyring（Tauri `tauri-plugin-stronghold` / Electron `keytar`）；首次启动引导填入 |
| R9 | **PyInstaller hidden imports 漏掉** | 运行时偶发 ImportError | CI 加一步「frozen build 跑全量 pytest 」smoke test |
| R10 | **SMTP 必填假设** | 当前 `delivery/adapters/email.py:29` 直接读 `settings.EMAIL_HOST`，未配则崩 | 见 §7 耦合点 #1 |
| R11 | **LLM API 强在线** | 离线状态下 `interpret/llm.py:43` raise，整个 pipeline 挂 | 桌面 app 显式声明「需在线」；网络故障 graceful degrade（已 tenacity retry 3 次） |
| R12 | **数据目录迁移破坏性升级** | 后续从「文件 jsonl」迁到「SQLite ORM」时数据兼容 | 升级脚本走 `migrate` + 一次性 import jsonl 到表；版本号写到 `data_dir/.schema_version` |

---

## 6. Tauri 失败决策点清单（满足任一即切 Electron）

| # | 量化判定条件 | 检测方法 |
|---|-------------|---------|
| F1 | Windows 实测 PyInstaller sidecar 启动失败率 > 5% | 在 Win10/11 三台干净机器各启动 100 次，统计未在 30s 内 listen 成功的次数 |
| F2 | macOS 公证 + Tauri updater 双签 跑通成本 > 3 人日 | 实施 packaging ft 时计时 |
| F3 | Linux WebKitGTK 在 Ubuntu 20.04 / 22.04 / Fedora 39 任一发行版无法显示前端 | 三发行版 smoke test 必须 100% 通过 |
| F4 | 总安装包（含签名）> 250 MB | release artifact 实测 |
| F5 | sidecar 进程残留率 > 1%（关 app 后 ps 查 python 进程） | Win/macOS 各 200 次启停脚本，残留 ≥ 3 次即 fail |
| F6 | Tauri 2.x sidecar plugin 在调研时存在 P0 unfix bug 阻塞功能 | 检查 [tauri-apps/plugins-workspace](https://github.com/tauri-apps/plugins-workspace) issues label `S-blocking` |
| F7 | 跨平台构建脚本需手动维护 > 3 处差异（不算 PyInstaller --target-arch） | 数 `tauri.conf.json` + spec 文件中 `if platform == ...` 分支 |
| F8 | Tauri 假阳率（Windows Defender 直接 quarantine 已签名 .msi） > 10% | 上传 [VirusTotal](https://www.virustotal.com/) 看 70 引擎中报毒数；EV 签名后仍 > 7 个引擎报即 fail |
| F9 | WebView2 在 Win10 LTSC（无系统 WebView2）一键解决方案缺失 | 实测 Win10 LTSC 1809 + Bootstrapper 是否能装上 |

**任一命中 → 切 Electron**。Electron 在 F1/F3/F5/F6/F8/F9 上明显更稳，代价是 F4 上 +80MB（可接受）。

---

## 7. 现状违反单机 app 假设的耦合点（实际扫描）

| # | 耦合点 | 文件 / 行号 | 现状描述 | 单机化方向 |
|---|--------|------------|---------|-----------|
| C1 | **SMTP 远程依赖必填** | `delivery/adapters/email.py:29-32`、`config/settings.py:87-94` | `EMAIL_HOST` 默认空字符串，未配置时投递失败但不报错（`get_connection(host="", ...)` 抛 SMTP 异常）。单机用户没自己 SMTP 服务器是常态 | (a) onboarding 引导用户填三方 SMTP（Gmail/腾讯企业邮 SMTP）；(b) 邮件 adapter 提供 fallback：写本地 .eml 文件到 `~/Downloads/explore-os-digest-<date>.eml` 让用户自己拖到邮件客户端；(c) 长期：飞书/微信 adapter 上线后弱化邮件刚需 |
| C2 | **LLM API 强外网依赖** | `interpret/llm.py:43-44`、`interpret/embedding.py:43-44`、`config/settings.py:78-83` | `LLMError("LLM_API_KEY is not configured")` 直接 raise；`LLM_API_BASE` 默认 `https://api.openai.com/v1` | 单机不可避免（设计原则：LLM 是必需）。首次启动 onboarding 强制填 API key + 测试连通；key 存 keyring |
| C3 | **DATABASE_URL 默认 PG** | `config/settings.py:60-65` | 默认 `postgres://explore:explore@localhost:5432/explore_os`；frozen exe 跑起来直接连不上 | 改默认为 SQLite `file:///<appdata>/explore_os.sqlite3`；env 覆盖保留 |
| C4 | **BASE_DIR 假设源码可写** | `subscriptions/memory.py:22`、`sources/pdf_fetcher.py:29`、`interpret/figure_extractor.py`（推测） | `BASE_DIR / "media"` 在 frozen exe 里是 `_MEIPASS` 临时目录或 Program Files（无写权限） | 引入 `EXPLORE_OS_DATA_DIR` setting，统一所有写路径；默认 `appdirs.user_data_dir` |
| C5 | **subscriptions.yaml 当前工作目录相对** | `subscriptions/management/commands/run_subscription.py:81`、`subscriptions/loader.py:42` | `Path("subscriptions.yaml")` 走 CWD；frozen 后 CWD 不确定 | 默认从 `EXPLORE_OS_CONFIG_DIR / "subscriptions.yaml"` 读；首启从 bundle 里的 `subscriptions.example.yaml` 拷贝 |
| C6 | **ALLOWED_HOSTS 仅含 localhost / 127.0.0.1** | `config/settings.py:14` | 单机这反而是好事 | ✅ 不需改 |
| C7 | **httpx 依赖外网** | `sources/pdf_fetcher.py:11`、`sources/fetchers/{arxiv,hf_papers}.py`、`interpret/{llm,embedding}.py` | arxiv.org / huggingface.co / LLM API 都需公网 | 单机用户必须有网络。只需在网络故障时 graceful（已用 tenacity） |
| C8 | **docker-compose.yml 描述 PG 服务** | `docker-compose.yml:1-21` | 单机 release 不应含此 | release 流水线排除；标注「dev only」 |
| C9 | **DJANGO_SECRET_KEY 默认 hardcoded** | `config/settings.py:12` | `default="dev-insecure-change-me"` 单机 release 也得是固定 dev key？还是首启生成？ | 首启生成 random key 写到 `EXPLORE_OS_CONFIG_DIR / .secret_key`，不写 .env |
| C10 | **TIME_ZONE = "Asia/Shanghai"** | `config/settings.py:70` | 海外用户错乱 | onboarding 让用户选；存 settings override |
| C11 | **EMAIL_TO_DEFAULT 单收件人假设** | `config/settings.py:95` | 多用户场景误推 | 单机本来就是单用户，OK；onboarding 引导填 |
| C12 | **media/ 在 git 仓库内 + 测试 fixture 共用此路径** | （现有 `.gitignore` 已忽略 media/，OK） | — | ✅ 已处理 |

**清理 backlog 大小**：12 个耦合点，C1/C3/C4/C5/C9 是必修（阻塞性），其余按重要性排。**预估单机化基础改造工作量：3–5 人日**（不含前端）。

---

## 下一步推荐路径

**走 Tauri**。证据链：(1) 现有代码层面对单机化几乎零阻碍——models.py 全空、零 PG-only 用法、数据已在文件系统，预计 SQLite 切换零 ORM patch；(2) 前端 v1.0 还未起步，可以从 day 1 强制 `bridge.ts` 抽象，把 Tauri/Electron 切换成本压到 1–2 人日；(3) Tauri 2.x sidecar + PyInstaller Django 在 2025–2026 已是社区成熟模式（dieharders 范例、awesome-tauri 多个生产案例）；(4) 主要风险是 Windows Defender 假阳和 macOS 公证，都是工程问题不是架构问题。**新建 ft（建议 ft-023 packaging-impl）实施时**，先按 §7 清单做 12 个耦合点的清理 + 切 SQLite + 加 APScheduler 入口（**不引入前端、不 PyInstaller**），全部跑通 pytest，再单开 ft 做 Tauri shell + 前端最小骨架 + PyInstaller spec + CI 三平台 build。**Electron 兜底门槛**按 §6 九条决策点客观判定，避免在 Tauri 跌跌撞撞做完才发现做不动。

---

## 参考链接

- [Tauri 2.0 Stable Release](https://v2.tauri.app/blog/tauri-20/)
- [Tauri Embedding External Binaries (sidecar)](https://v2.tauri.app/develop/sidecar/)
- [tauri-apps/tauri Discussion #2759 — Embed Python sidecar](https://github.com/tauri-apps/tauri/discussions/2759)
- [tauri-apps/tauri Discussion #3060 — Django sidecar pattern](https://github.com/tauri-apps/tauri/discussions/3060)
- [example-tauri-v2-python-server-sidecar](https://github.com/dieharders/example-tauri-v2-python-server-sidecar)
- [Tauri in 2026: Build Cross-Platform Desktop Apps (DEV)](https://dev.to/ottoaria/tauri-in-2026-build-cross-platform-desktop-apps-with-web-technologies-better-than-electron-11mo)
- [PyInstaller Recipe: Executable From Django](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Executable-From-Django)
- [PyInstaller Common Issues and Pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
- [electron-python-example](https://github.com/fyears/electron-python-example)
- [Bundling Python inside an Electron app — Simon Willison's TILs](https://til.simonwillison.net/electron/python-inside-electron)
- [Tauri Windows Defender false positive #2486](https://github.com/tauri-apps/tauri/issues/2486)
- [Tauri MSI false positives #4749](https://github.com/tauri-apps/tauri/issues/4749)
- [Lightweight Django Task Queues in 2025 (Medium)](https://medium.com/@g.suryawanshi/lightweight-django-task-queues-in-2025-beyond-celery-74a95e0548ec)
- [Building Production-Ready Desktop LLM Apps: Tauri, FastAPI, PyInstaller](https://aiechoes.substack.com/p/building-production-ready-desktop)
