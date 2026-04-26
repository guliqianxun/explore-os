# explore-os Electron shell (ft-023)

Electron main process + Python (Django + Waitress) sidecar. The frontend UI
itself lives in ft-024; this folder only contains the shell + sidecar wiring.

## Layout

```
electron/
├── package.json
├── tsconfig.json
├── src/
│   ├── main.ts        # Electron main: window + lifecycle + IPC
│   ├── preload.ts     # contextBridge -> window.explore
│   ├── sidecar.ts     # spawn / health-check / kill the Python child
│   ├── port.ts        # parse "listening on" banner + /api/health/ poll
│   └── types.ts       # shared types
├── resources/
│   └── placeholder.html  # shown until ft-024 ships the React UI
└── build/
    ├── electron-builder.yml
    └── icons/             # icon.ico / icon.icns / icon.png (TBD)
```

The PyInstaller spec (`build/sidecar-cuda.spec`) and the entry point
(`sidecar_entry.py`) live at the repo root, not here.

## Prerequisites

* Node.js 20+ and npm
* Python toolchain set up via `uv sync` at the repo root (Python 3.12)
* Windows for the CUDA bundle; macOS / Linux paths covered but not the
  primary target this milestone.

## Dev loop

From the repo root:

```bash
uv sync                       # ensures pyinstaller + waitress are installed
cd electron
npm install                   # one-off
npm run dev:electron          # tsc compile, then launch Electron
```

`dev:electron` boots the sidecar via `uv run python sidecar_entry.py
--data-dir <userData> --port 0`. Watch for the line

```
[sidecar] listening on http://127.0.0.1:<port>
```

The main process parses that line, polls `/api/health/`, then opens the
BrowserWindow. The placeholder page calls `window.explore.getBackendPort()`
to surface the chosen port.

To start only the sidecar (e.g. for `curl` / Postman):

```bash
npm run dev:sidecar           # cd .. && uv run python sidecar_entry.py …
```

## Production build (CUDA bundle, self-use)

```bash
cd electron
npm run build:all
```

That runs in two stages:

1. `build:sidecar` → `uv run pyinstaller build/sidecar-cuda.spec --noconfirm
   --distpath dist`. Output lands in `<repo>/dist/explore-os-sidecar/`
   (one-folder mode). Expect ~1.5 GB with CUDA torch + docling.
2. `build:electron` → `tsc` then `electron-builder --config
   build/electron-builder.yml`. The PyInstaller folder is copied verbatim
   into `<app>/resources/sidecar/` via `extraResources`.

Outputs:

* Windows: `electron/dist/*.exe` (NSIS installer)
* macOS: `electron/dist/*.dmg` (unsigned, self-use)
* Linux: `electron/dist/*.AppImage`

> Code signing / notarization is deliberately skipped at the self-use stage
> (see `CLAUDE.md` "桌面端栈"). v1.x will revisit before public distribution.

## How the wiring works

```
+---------------+   spawn(uv run python sidecar_entry.py --port 0)
| Electron main | ───────────────────────────────────────────────► sidecar (Waitress)
|  main.ts      | ◄── stdout: "[sidecar] listening on http://…:54321" ──
|  sidecar.ts   |
+-------+-------+
        │ ipcMain.handle("explore:get-backend-port", …)
        ▼
+---------------+
|  preload.ts   |  contextBridge.exposeInMainWorld("explore", …)
+-------+-------+
        ▼
+---------------+
|  renderer     |  const port = await window.explore.getBackendPort();
|  (ft-024)     |  fetch(`http://127.0.0.1:${port}/api/papers/`)
+---------------+
```

* **Port discovery**: sidecar binds `port=0`, OS picks a free port,
  Waitress reports it; the main process parses the banner.
* **Health check**: after the banner, `port.ts` polls `/api/health/` for
  up to 30 seconds before declaring the sidecar `ready`.
* **Cleanup**: `stopSidecar()` runs on `window-all-closed` and
  `before-quit`. Windows uses `taskkill /F /T /PID` to reap the
  PyInstaller bootloader's grandchildren; unix sends `SIGTERM` then
  `SIGKILL` after a 5 s grace.
* **Data dir**: `app.getPath("userData")` is forwarded as
  `EXPLORE_OS_DATA_DIR`, which steers `apps.core.paths` (and therefore
  `HF_HOME` / `TRANSFORMERS_CACHE`) to a writable per-user tree — frozen
  exes can't write next to themselves.

## Sandbox limitation note

This was scaffolded by an agent without Node or PyInstaller available;
`npm install`, `tsc`, `electron`, and `pyinstaller` have **not** been
exercised in CI. Validate locally on first run.
