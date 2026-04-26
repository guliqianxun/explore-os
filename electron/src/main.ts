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
  // Prod (and dev without UI): load the placeholder shipped under resources/.
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    await mainWindow.loadURL(devUrl);
  } else {
    await mainWindow.loadFile(
      path.join(__dirname, "..", "resources", "placeholder.html"),
    );
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
