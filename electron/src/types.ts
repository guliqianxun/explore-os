// ft-023: shared types between Electron main / preload / renderer.

/** Status of the Python sidecar lifecycle. */
export type SidecarStatus =
  | "idle"
  | "starting"
  | "ready"
  | "stopping"
  | "stopped"
  | "error";

export interface SidecarInfo {
  status: SidecarStatus;
  /** TCP port the Django sidecar bound to (only valid once `status === "ready"`). */
  port: number | null;
  /** Last error message, populated when `status === "error"`. */
  error?: string;
}

/**
 * API surface exposed by `preload.ts` to the renderer via `contextBridge`.
 * Renderer accesses it as `window.explore.<method>()`.
 */
export interface ExploreBridge {
  getBackendPort(): Promise<number | null>;
  getSidecarStatus(): Promise<SidecarInfo>;
  /** 通过系统浏览器打开外链（arxiv / pdf 下载等） */
  openExternal(url: string): Promise<void>;
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  interface Window {
    explore: ExploreBridge;
  }
}
