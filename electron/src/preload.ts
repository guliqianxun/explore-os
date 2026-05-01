// ft-023: contextBridge — exposes a safe, narrow API to the renderer.
//
// Renderer code reaches the sidecar's HTTP base URL via:
//
//   const port = await window.explore.getBackendPort();
//   const baseURL = `http://127.0.0.1:${port}`;
//
// `contextIsolation: true` + `nodeIntegration: false` are set in main.ts;
// nothing here directly hands the renderer access to Node APIs.

import { contextBridge, ipcRenderer } from "electron";

import type { DataDirInfo, ExploreBridge, SidecarInfo } from "./types";

const bridge: ExploreBridge = {
  getBackendPort: () =>
    ipcRenderer.invoke("explore:get-backend-port") as Promise<number | null>,
  getSidecarStatus: () =>
    ipcRenderer.invoke("explore:get-sidecar-status") as Promise<SidecarInfo>,
  openExternal: (url: string) =>
    ipcRenderer.invoke("explore:open-external", url) as Promise<void>,
  notify: (opts) =>
    ipcRenderer.invoke("explore:notify", opts) as Promise<void>,
  onNotificationClick: (handler) => {
    const listener = (_e: unknown, jobId: string | null) => handler(jobId);
    ipcRenderer.on("explore:notification-clicked", listener);
    return () => ipcRenderer.off("explore:notification-clicked", listener);
  },
  getDataDirInfo: () =>
    ipcRenderer.invoke("explore:get-data-dir-info") as Promise<
      DataDirInfo | null
    >,
  setDataDirOverride: (override) =>
    ipcRenderer.invoke("explore:set-data-dir-override", override) as Promise<{
      ok: boolean;
    }>,
  pickDirectory: () =>
    ipcRenderer.invoke("explore:pick-directory") as Promise<string | null>,
};

contextBridge.exposeInMainWorld("explore", bridge);
