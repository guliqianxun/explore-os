// ft-023: Python sidecar lifecycle (spawn / health-check / kill).
//
// Dev mode  : `uv run python sidecar_entry.py --data-dir <userData> --port 0`
//             (cwd = project root, two dirs up from `dist-electron`).
// Prod mode : `<resourcesPath>/sidecar/explore-os-sidecar(.exe)`
//             (PyInstaller one-folder bundle copied in by electron-builder).
//
// Process cleanup:
//   * Windows: `taskkill /F /T /PID <pid>` to also reap grandchildren
//              (the PyInstaller bootloader spawns the actual process).
//   * unix   : SIGTERM, then SIGKILL after a 5s grace.
//
// Port discovery:
//   sidecar is told `--port 0` and prints `[sidecar] listening on http://...`
//   we parse that line, then poll `/api/health/` until it answers 200.

import { spawn, ChildProcess } from "child_process";
import { app } from "electron";
import * as path from "path";

import { parseListeningLine, waitForHealth } from "./port";
import { SidecarInfo } from "./types";

const HEALTH_TIMEOUT_MS = 30_000; // 30s — covers Django boot + first migrate
const PORT_TIMEOUT_MS = 30_000;
const KILL_GRACE_MS = 5_000;

let proc: ChildProcess | null = null;
let info: SidecarInfo = { status: "idle", port: null };

export function getSidecarInfo(): SidecarInfo {
  return { ...info };
}

/**
 * Spawn the sidecar, wait for `[sidecar] listening on …` and a healthy
 * `/api/health/`. Returns the port. Throws (and updates `info.status`)
 * on any failure.
 */
export async function startSidecar(): Promise<number> {
  if (proc) {
    throw new Error("sidecar already running");
  }
  info = { status: "starting", port: null };

  const dataDir = app.getPath("userData");
  const isDev = !app.isPackaged;

  let cmd: string;
  let args: string[];
  let cwd: string | undefined;

  if (isDev) {
    // Project root is two dirs up from compiled `dist-electron/sidecar.js`.
    const projectRoot = path.resolve(__dirname, "..", "..");
    // Prefer the in-repo venv python so we don't trigger a uv re-sync on
    // every dev launch (uv would otherwise try to re-resolve packages on
    // restricted networks, e.g. behind a SOCKS proxy where the CUDA torch
    // mirror times out). Fall back to `uv run python` only if the venv
    // is missing.
    const venvPy =
      process.platform === "win32"
        ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
        : path.join(projectRoot, ".venv", "bin", "python");
    const fs = require("fs") as typeof import("fs");
    if (fs.existsSync(venvPy)) {
      cmd = venvPy;
      args = ["sidecar_entry.py", "--data-dir", dataDir, "--port", "0"];
    } else {
      cmd = "uv";
      args = [
        "run",
        "python",
        "sidecar_entry.py",
        "--data-dir",
        dataDir,
        "--port",
        "0",
      ];
    }
    cwd = projectRoot;
  } else {
    const exe =
      process.platform === "win32"
        ? "explore-os-sidecar.exe"
        : "explore-os-sidecar";
    cmd = path.join(process.resourcesPath, "sidecar", exe);
    args = ["--data-dir", dataDir, "--port", "0"];
    cwd = undefined;
  }

  proc = spawn(cmd, args, {
    cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    // Windows: `uv` resolves through PATH only when shell:true.
    shell: isDev && process.platform === "win32",
    windowsHide: true,
  });

  const child = proc;

  child.on("exit", (code, signal) => {
    console.log(`[sidecar] process exited code=${code} signal=${signal}`);
    if (info.status !== "stopping") {
      info = { status: "error", port: null, error: `exit ${code ?? signal}` };
    } else {
      info = { status: "stopped", port: null };
    }
    proc = null;
  });
  child.on("error", (err) => {
    console.error("[sidecar] spawn error", err);
    info = { status: "error", port: null, error: String(err) };
  });

  try {
    const port = await waitForListeningLine(child, PORT_TIMEOUT_MS);
    await waitForHealth(port, HEALTH_TIMEOUT_MS);
    info = { status: "ready", port };
    return port;
  } catch (e) {
    info = { status: "error", port: null, error: String(e) };
    stopSidecar();
    throw e;
  }
}

export function stopSidecar(): void {
  if (!proc || proc.killed) {
    proc = null;
    if (info.status !== "error") info = { status: "stopped", port: null };
    return;
  }
  info = { status: "stopping", port: info.port };
  const child = proc;
  if (process.platform === "win32" && child.pid) {
    // /F = force, /T = include child tree.
    spawn("taskkill", ["/F", "/T", "/PID", String(child.pid)], {
      windowsHide: true,
    });
  } else {
    child.kill("SIGTERM");
    setTimeout(() => {
      if (child && !child.killed) {
        child.kill("SIGKILL");
      }
    }, KILL_GRACE_MS);
  }
  proc = null;
}

/**
 * Buffer stdout/stderr line-wise; resolve when the listening banner is
 * seen, reject on timeout or if the process dies first.
 */
function waitForListeningLine(
  child: ChildProcess,
  timeoutMs: number,
): Promise<number> {
  return new Promise<number>((resolve, reject) => {
    let stdoutBuf = "";
    let stderrBuf = "";
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      child.stdout?.off("data", onStdout);
      child.stderr?.off("data", onStderr);
      child.off("exit", onExit);
      fn();
    };

    const onStdout = (chunk: Buffer | string) => {
      const text = typeof chunk === "string" ? chunk : chunk.toString("utf8");
      stdoutBuf += text;
      // Mirror to console for dev visibility.
      process.stdout.write(`[sidecar:out] ${text}`);
      let nl: number;
      while ((nl = stdoutBuf.indexOf("\n")) >= 0) {
        const line = stdoutBuf.slice(0, nl).trimEnd();
        stdoutBuf = stdoutBuf.slice(nl + 1);
        const port = parseListeningLine(line);
        if (port !== null) {
          finish(() => resolve(port));
          return;
        }
      }
    };

    const onStderr = (chunk: Buffer | string) => {
      const text = typeof chunk === "string" ? chunk : chunk.toString("utf8");
      stderrBuf += text;
      process.stderr.write(`[sidecar:err] ${text}`);
      // Sidecar may, in some configurations, log the banner to stderr.
      let nl: number;
      while ((nl = stderrBuf.indexOf("\n")) >= 0) {
        const line = stderrBuf.slice(0, nl).trimEnd();
        stderrBuf = stderrBuf.slice(nl + 1);
        const port = parseListeningLine(line);
        if (port !== null) {
          finish(() => resolve(port));
          return;
        }
      }
    };

    const onExit = (code: number | null, signal: NodeJS.Signals | null) => {
      finish(() =>
        reject(
          new Error(
            `sidecar exited before becoming ready (code=${code} signal=${signal})`,
          ),
        ),
      );
    };

    child.stdout?.on("data", onStdout);
    child.stderr?.on("data", onStderr);
    child.once("exit", onExit);

    const timer = setTimeout(() => {
      finish(() =>
        reject(
          new Error(
            `timed out (${timeoutMs}ms) waiting for sidecar 'listening on' banner`,
          ),
        ),
      );
    }, timeoutMs);
  });
}
