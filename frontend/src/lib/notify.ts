// ft-031: 桌面通知抽象层。
//
// Electron prod：走 main IPC `explore:notify`（系统级 toast，OS 通知中心
// 可见，点击聚焦窗口）。
// 浏览器 dev (`npm run dev`)：回退到 `window.Notification`，首次需用户授权。
//
// 点击行为约定：
// - Electron：main 进程 send `explore:notification-clicked` → 由
//   `onNotificationClick` 订阅者跳路由（HashRouter）。
// - 浏览器：直接挂 `notification.onclick`。

export interface NotifyOptions {
  title: string;
  body: string;
  /** 关联的 job_id，传给点击回调让前端决定跳哪页。 */
  jobId?: string;
}

const STORAGE_KEY = "explore-os.notify.permission-asked";

function hasElectronBridge(): boolean {
  return typeof window !== "undefined" && !!window.explore?.notify;
}

async function ensureBrowserPermission(): Promise<NotificationPermission> {
  if (typeof Notification === "undefined") return "denied";
  if (Notification.permission === "granted") return "granted";
  if (Notification.permission === "denied") return "denied";
  // 防止每次跑都弹权限框：localStorage 记一次
  try {
    const asked = localStorage.getItem(STORAGE_KEY);
    if (asked === "1" && Notification.permission === "default") {
      return "default";
    }
  } catch {
    // localStorage 不可用（隐私模式等）— 直接请求
  }
  try {
    const p = await Notification.requestPermission();
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    return p;
  } catch {
    return "denied";
  }
}

export async function notify(opts: NotifyOptions): Promise<void> {
  if (hasElectronBridge()) {
    await window.explore!.notify!(opts);
    return;
  }
  const perm = await ensureBrowserPermission();
  if (perm !== "granted") return;
  const n = new Notification(opts.title, { body: opts.body });
  n.onclick = () => {
    window.focus();
    // 点击通知 = 跳未决区（与 Electron 路径行为一致；订阅者用统一 hook 处理）
    window.location.hash = "#/papers?status=new";
  };
}

/**
 * 订阅"通知点击"事件。Electron 走 main IPC；浏览器没有持久化通道，回退为
 * 直接在 `notify()` 里挂 onclick — 此处提供 noop 解绑（不会触发，但接口
 * 一致）。返回 unsubscribe。
 */
export function onNotificationClick(
  handler: (jobId: string | null) => void,
): () => void {
  if (typeof window !== "undefined" && window.explore?.onNotificationClick) {
    return window.explore.onNotificationClick(handler);
  }
  return () => {};
}
