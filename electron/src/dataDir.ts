// ft-037: 数据目录解析 + launcher.json 持久化。
//
// Why launcher.json (与 sidecar 的 user_config.json 解耦):
//   sidecar 的 ``user_config.json`` 在 ``<data_dir>/user_config.json``，
//   而我们想让 ``data_dir`` 本身可配 — 鸡生蛋。所以把 "data_dir 选哪个"
//   单独存到 ``<electron userData>/launcher.json``，Electron main 读，
//   sidecar 完全不见。
//
// 优先级（高 → 低）:
//   1. launcher.json.data_dir          (用户在 Settings 页填的)
//   2. EXPLORE_OS_DATA_DIR env         (CI / 高级用户 export)
//   3. PORTABLE_EXECUTABLE_DIR + /data (electron-builder portable target 注入)
//   4. 平台默认 (%APPDATA%/explore-os 等) — 跟 apps/core/paths.py 对齐

import * as fs from "fs";
import * as os from "os";
import * as path from "path";

export interface LauncherConfig {
  /** 用户显式覆盖。null / 空 = 不覆盖，走优先级链路 2/3/4。 */
  data_dir: string | null;
}

export type DataDirSource =
  | "user_override"
  | "env"
  | "portable"
  | "platform_default";

export interface DataDirInfo {
  /** 最终生效的绝对路径 */
  effective: string;
  /** 命中哪一层 */
  source: DataDirSource;
  /** 用户当前的覆盖值（可能与 effective 不同 — 当覆盖路径不可写时回退） */
  user_override: string | null;
  /** 是否运行在 portable exe 下 */
  portable: boolean;
  /** portable 模式下的 exe 目录 */
  portable_dir: string | null;
}

const LAUNCHER_FILENAME = "launcher.json";

function isPortable(): boolean {
  return Boolean(process.env.PORTABLE_EXECUTABLE_DIR);
}

function portableDir(): string | null {
  return process.env.PORTABLE_EXECUTABLE_DIR || null;
}

/**
 * 平台默认 — 与 ``apps/core/paths.py::data_dir()`` 对齐，避免 Electron 看到的
 * userData 跟 sidecar 看到的 EXPLORE_OS_DATA_DIR 漂移。
 */
export function platformDefaultDataDir(): string {
  if (process.platform === "win32") {
    const appdata = process.env.APPDATA;
    const base = appdata || path.join(os.homedir(), ".config");
    return path.join(base, "explore-os");
  }
  if (process.platform === "darwin") {
    return path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "explore-os",
    );
  }
  return path.join(os.homedir(), ".config", "explore-os");
}

/**
 * Electron userData 目录 — 在 ``app.whenReady`` 前调用 ``app.setPath`` 时使用。
 * portable 模式下挂在 exe 同目录，非 portable 走平台默认。
 *
 * launcher.json 存这里。注意它不一定等于 effective data_dir（用户可能覆盖到
 * 别处，但 launcher.json 本身要落在一个可被 Electron 找到的稳定位置）。
 */
export function electronUserDataDir(): string {
  if (isPortable() && portableDir()) {
    return path.join(portableDir()!, "electron-data");
  }
  return platformDefaultDataDir();
}

function launcherConfigPath(): string {
  return path.join(electronUserDataDir(), LAUNCHER_FILENAME);
}

export function readLauncherConfig(): LauncherConfig {
  const p = launcherConfigPath();
  try {
    if (!fs.existsSync(p)) return { data_dir: null };
    const raw = fs.readFileSync(p, "utf8");
    const obj = JSON.parse(raw) as Partial<LauncherConfig>;
    return { data_dir: typeof obj.data_dir === "string" ? obj.data_dir : null };
  } catch (err) {
    console.warn("[dataDir] failed to read launcher.json:", err);
    return { data_dir: null };
  }
}

export function writeLauncherConfig(cfg: LauncherConfig): void {
  const p = launcherConfigPath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = p + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(cfg, null, 2), "utf8");
  fs.renameSync(tmp, p);
}

function canWriteDir(p: string): boolean {
  try {
    fs.mkdirSync(p, { recursive: true });
    const probe = path.join(p, ".write-probe");
    fs.writeFileSync(probe, "");
    fs.unlinkSync(probe);
    return true;
  } catch {
    return false;
  }
}

/**
 * 主入口 — 算出 effective data_dir 和它来自哪一层。永远返回有效目录
 * （已 mkdir，已通过写探测）。最坏情况回退 platform default。
 */
export function resolveDataDir(): DataDirInfo {
  const launcher = readLauncherConfig();
  const portable = isPortable();
  const portable_dir = portableDir();

  const candidates: Array<{ path: string; source: DataDirSource }> = [];
  if (launcher.data_dir) {
    candidates.push({ path: launcher.data_dir, source: "user_override" });
  }
  if (process.env.EXPLORE_OS_DATA_DIR) {
    candidates.push({
      path: process.env.EXPLORE_OS_DATA_DIR,
      source: "env",
    });
  }
  if (portable && portable_dir) {
    candidates.push({
      path: path.join(portable_dir, "data"),
      source: "portable",
    });
  }
  candidates.push({
    path: platformDefaultDataDir(),
    source: "platform_default",
  });

  for (const c of candidates) {
    if (canWriteDir(c.path)) {
      return {
        effective: c.path,
        source: c.source,
        user_override: launcher.data_dir,
        portable,
        portable_dir,
      };
    }
  }
  // 所有候选都不可写 — 极端情况，强行用 platform default（mkdir 已尝试过）
  const fallback = platformDefaultDataDir();
  return {
    effective: fallback,
    source: "platform_default",
    user_override: launcher.data_dir,
    portable,
    portable_dir,
  };
}
