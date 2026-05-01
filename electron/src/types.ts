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

/** ft-037: 数据目录解析结果（Electron main 算出来后给 Settings 页展示）。 */
export type DataDirSource =
  | "user_override"
  | "env"
  | "portable"
  | "platform_default";

export interface DataDirInfo {
  effective: string;
  source: DataDirSource;
  user_override: string | null;
  portable: boolean;
  portable_dir: string | null;
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
  /** ft-031: 触发 OS 桌面通知（Win 11 toast / macOS notification center）。 */
  notify(opts: { title: string; body: string; jobId?: string }): Promise<void>;
  /** ft-031: 通知点击回调（用户点 toast → main 聚焦窗口并通过此通道告诉
   * renderer 跳路由）。返回 unsubscribe 函数。 */
  onNotificationClick(handler: (jobId: string | null) => void): () => void;
  /** ft-037: 当前 effective 数据目录信息（Settings 页展示）。 */
  getDataDirInfo(): Promise<DataDirInfo | null>;
  /** ft-037: 写入 launcher.json.data_dir。null/空 = 清除覆盖。需重启生效。 */
  setDataDirOverride(override: string | null): Promise<{ ok: boolean }>;
  /** ft-037: 弹原生目录选择器，返回选定路径或 null（取消）。 */
  pickDirectory(): Promise<string | null>;
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  interface Window {
    explore: ExploreBridge;
  }
}
