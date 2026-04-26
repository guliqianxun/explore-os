# explore-os frontend (ft-024)

Vite + React 18 + TypeScript + Tailwind 3 + shadcn/ui SPA. Talks to the
Python sidecar (Django + Waitress) via `http://127.0.0.1:<port>/api`. The
port is discovered at runtime through `window.explore.getBackendPort()`
(exposed by `electron/src/preload.ts`); when running in a plain browser
for debug it falls back to `http://127.0.0.1:8000`.

## Pages

1. **PaperListPage** — `/` — papers + counts (`/api/papers/`).
2. **PaperDetailPage** — `/papers/:id` — three columns:
   - left 250px: section tree
   - center: docling markdown via `react-markdown` + `rehype-katex`
   - right 400px: `ClaimCard` list (KaTeX-rendered equations + counter
     signals + cite badges)
3. **SubscriptionPage** — `/subscriptions` — list / edit (placeholder
   endpoints, full CRUD lands in a follow-up)
4. **RunPage** — `/run` — trigger extract / interpret / render and poll
   `/api/jobs/<id>/`

The graph visualisation is permanently deferred to v1.x — there is no
Excalidraw embed.

## Develop

```bash
# 1. install deps (Node 22 + npm 10)
cd frontend
npm install

# 2. start the Vite dev server (terminal 1)
npm run dev          # http://127.0.0.1:5173

# 3. start the Electron shell (terminal 2)
cd ../electron
# Windows cmd
set VITE_DEV_SERVER_URL=http://127.0.0.1:5173 && npm run dev:electron
# PowerShell
$env:VITE_DEV_SERVER_URL = "http://127.0.0.1:5173"; npm run dev:electron
# bash
VITE_DEV_SERVER_URL=http://127.0.0.1:5173 npm run dev:electron
```

When `VITE_DEV_SERVER_URL` is set the Electron main process loads the dev
server URL; otherwise it loads `frontend/dist/index.html`.

## Production build

```bash
cd frontend && npm run build         # → frontend/dist/
cd ../electron && npm run build:all  # PyInstaller sidecar + electron-builder
```

`electron/build/electron-builder.yml` already lists `frontend/dist/**/*`
in `files`, so the SPA ships inside the asar.

## Standalone web debug

If you want to poke the SPA in a normal browser without Electron, run the
Django sidecar on port 8000 (`uv run python sidecar_entry.py --data-dir
./data-dev --port 8000`) — `window.explore` is missing in a plain browser
so the API client falls back to `127.0.0.1:8000`.

## Layout

```
frontend/
├── index.html
├── package.json
├── vite.config.ts / tailwind.config.ts / postcss.config.js / tsconfig*.json
├── components.json                      # shadcn/ui config
└── src/
    ├── main.tsx
    ├── App.tsx                          # React Router
    ├── styles/globals.css               # Tailwind + shadcn vars
    ├── lib/utils.ts                     # cn()
    ├── api/
    │   ├── client.ts                    # axios instance
    │   ├── papers.ts
    │   ├── subscriptions.ts
    │   └── jobs.ts
    ├── stores/jobsStore.ts              # Zustand: in-flight jobs
    ├── components/
    │   ├── ui/                          # shadcn copies (button/card/...)
    │   ├── PaperCard.tsx
    │   ├── ClaimCard.tsx                # core
    │   ├── MarkdownView.tsx
    │   ├── SectionTree.tsx
    │   ├── CounterSignalBadge.tsx
    │   └── EquationBlock.tsx            # <BlockMath> with try/catch fallback
    └── pages/
        ├── PaperListPage.tsx
        ├── PaperDetailPage.tsx
        ├── SubscriptionPage.tsx
        └── RunPage.tsx
```
