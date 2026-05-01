// ft-023: Electron main process entry.
//
// Lifecycle:
//   app.whenReady -> startSidecar -> createWindow
//   window-all-closed / before-quit -> stopSidecar
//
// IPC (renderer ⇄ main):
//   explore:get-backend-port    -> number | null
//   explore:get-sidecar-status  -> SidecarInfo

import {
  app,
  BrowserWindow,
  Menu,
  Notification,
  dialog,
  ipcMain,
  shell,
} from "electron";
import * as path from "path";

import { getSidecarInfo, startSidecar, stopSidecar } from "./sidecar";
import {
  electronUserDataDir,
  resolveDataDir,
  writeLauncherConfig,
  type DataDirInfo,
} from "./dataDir";

let mainWindow: BrowserWindow | null = null;
let sidecarPort: number | null = null;
let dataDirInfo: DataDirInfo | null = null;

async function createWindow(): Promise<void> {
  // No application menu — the React header is the only chrome.
  Menu.setApplicationMenu(null);

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: true,
    // Hide native title bar; OS still draws min/max/close as overlay buttons
    // on the right (Windows 11+). React header doubles as the drag region
    // via -webkit-app-region: drag (see App.tsx).
    titleBarStyle: "hidden",
    titleBarOverlay: {
      // Match the React header's bg-white so the overlay region blends in.
      color: "#ffffff",
      symbolColor: "#1c1a16",
      height: 40,
    },
    // Prevent flash of transparent content during boot — backstop with the
    // editorial cream paper bg from tokens.css (--bg).
    backgroundColor: "#fdfcf8",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Dev: load the Vite dev server (set by ft-024 dev script).
  // Prod: load the built Vite SPA from frontend/index.html.
  //
  // Dev:      <repo>/electron/dist-electron/main.js
  //           + <repo>/frontend/dist/index.html
  //           -> __dirname/../../frontend/dist/index.html
  // Packaged: <app>/resources/app.asar/dist-electron/main.js
  //           + <app>/resources/frontend/index.html  (extraResources)
  //           -> process.resourcesPath/frontend/index.html
  //
  // Parent-relative globs in `files` are silently dropped by electron-builder,
  // so the SPA ships via `extraResources` (see build/electron-builder.yml).
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    await mainWindow.loadURL(devUrl);
  } else {
    const indexHtml = app.isPackaged
      ? path.join(process.resourcesPath, "frontend", "index.html")
      : path.join(__dirname, "..", "..", "frontend", "dist", "index.html");
    await mainWindow.loadFile(indexHtml);
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function registerIpc(): void {
  ipcMain.handle("explore:get-backend-port", () => sidecarPort);
  ipcMain.handle("explore:get-sidecar-status", () => getSidecarInfo());
  // ft-037: data dir info (Settings 页用，决定显示什么)
  ipcMain.handle("explore:get-data-dir-info", () => dataDirInfo);
  // ft-037: 用户改路径 — 只写 launcher.json，不重启。前端弹"重启生效"。
  ipcMain.handle(
    "explore:set-data-dir-override",
    (_e, override: string | null) => {
      const trimmed = typeof override === "string" ? override.trim() : "";
      writeLauncherConfig({ data_dir: trimmed || null });
      return { ok: true };
    },
  );
  // ft-037: 原生目录选择器
  ipcMain.handle("explore:pick-directory", async () => {
    const r = await dialog.showOpenDialog(mainWindow ?? undefined!, {
      properties: ["openDirectory", "createDirectory"],
      title: "选择数据目录",
    });
    if (r.canceled || r.filePaths.length === 0) return null;
    return r.filePaths[0];
  });
  // 限制允许的协议（防止 file:// 之类的 LFI）
  ipcMain.handle("explore:open-external", async (_e, url: string) => {
    if (typeof url !== "string") return;
    if (!/^https?:\/\//i.test(url)) return;
    await shell.openExternal(url);
  });
  // ft-031: 桌面通知。click → 聚焦窗口 + 把 jobId 回投给 renderer，由前端
  // 决定路由（HashRouter，跳 #/papers?status=new）。
  ipcMain.handle(
    "explore:notify",
    (_e, opts: { title: string; body: string; jobId?: string }) => {
      if (!Notification.isSupported()) return;
      const n = new Notification({
        title: opts?.title ?? "explore-os",
        body: opts?.body ?? "",
        silent: false,
      });
      n.on("click", () => {
        if (mainWindow) {
          if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send(
            "explore:notification-clicked",
            opts?.jobId ?? null,
          );
        }
      });
      n.show();
    },
  );
}

async function bootstrap(): Promise<void> {
  registerIpc();
  // ft-037: 解析 effective data_dir，传给 sidecar via env
  dataDirInfo = resolveDataDir();
  console.log(
    `[main] data_dir=${dataDirInfo.effective} source=${dataDirInfo.source}` +
      (dataDirInfo.portable ? " (portable)" : ""),
  );
  try {
    sidecarPort = await startSidecar(dataDirInfo.effective);
    console.log(`[main] sidecar ready on port ${sidecarPort}`);
  } catch (err) {
    console.error("[main] sidecar failed to start", err);
    dialog.showErrorBox(
      "explore-os",
      `Python sidecar failed to start.\n\n${String(err)}`,
    );
    app.exit(1);
    return;
  }
  await createWindow();
}

// ft-024 follow-up: name the app "explore-os" so userData lives at
// %APPDATA%/explore-os (Windows) / ~/Library/Application Support/explore-os
// (macOS) / ~/.config/explore-os (Linux), instead of the default "Electron".
// Must run before app.requestSingleInstanceLock / app.whenReady so the lock
// file lives in the right directory too.
app.setName("explore-os");

// ft-037: portable 模式下 userData 重定向到 exe 同目录的 electron-data/，
// 让 single-instance lock 文件、launcher.json 等都跟 exe 走（U 盘场景单元化）。
// 必须在 ``app.requestSingleInstanceLock`` 之前。
try {
  app.setPath("userData", electronUserDataDir());
} catch (err) {
  console.warn("[main] setPath userData failed (continuing):", err);
}

// Single-instance guard — second launch should focus the existing window.
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(bootstrap);

  app.on("window-all-closed", () => {
    stopSidecar();
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });

  app.on("before-quit", () => {
    stopSidecar();
  });
}
