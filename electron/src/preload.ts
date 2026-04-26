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

import type { ExploreBridge, SidecarInfo } from "./types";

const bridge: ExploreBridge = {
  getBackendPort: () =>
    ipcRenderer.invoke("explore:get-backend-port") as Promise<number | null>,
  getSidecarStatus: () =>
    ipcRenderer.invoke("explore:get-sidecar-status") as Promise<SidecarInfo>,
};

contextBridge.exposeInMainWorld("explore", bridge);
