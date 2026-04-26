// ft-023: Electron main process entry.
//
// Lifecycle:
//   app.whenReady -> startSidecar -> createWindow
//   window-all-closed / before-quit -> stopSidecar
//
// IPC (renderer ⇄ main):
//   explore:get-backend-port    -> number | null
//   explore:get-sidecar-status  -> SidecarInfo

import { app, BrowserWindow, dialog, ipcMain } from "electron";
import * as path from "path";

import { getSidecarInfo, startSidecar, stopSidecar } from "./sidecar";

let mainWindow: BrowserWindow | null = null;
let sidecarPort: number | null = null;

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Dev: load the Vite dev server (set by ft-024 dev script).
  // Prod: load the built Vite SPA from frontend/dist/index.html. The path
  // resolves relative to dist-electron/main.js — the layout is:
  //
  //   <repo>/electron/dist-electron/main.js   (running file in dev)
  //   <repo>/frontend/dist/index.html         (Vite build output)
  //
  // In a packaged build, electron-builder is configured (build/electron-builder.yml)
  // to copy `frontend/dist/**/*` into the asar so the same relative layout
  // (`../../frontend/dist/index.html` from `dist-electron/main.js`) keeps working.
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    await mainWindow.loadURL(devUrl);
  } else {
    const indexHtml = path.join(
      __dirname,
      "..",
      "..",
      "frontend",
      "dist",
      "index.html",
    );
    await mainWindow.loadFile(indexHtml);
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function registerIpc(): void {
  ipcMain.handle("explore:get-backend-port", () => sidecarPort);
  ipcMain.handle("explore:get-sidecar-status", () => getSidecarInfo());
}

async function bootstrap(): Promise<void> {
  registerIpc();
  try {
    sidecarPort = await startSidecar();
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
