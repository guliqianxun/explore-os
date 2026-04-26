// ft-023: port helpers.
//
// We do not pre-pick a port from JS because the sidecar is told `--port 0`
// and prints the OS-assigned port to stdout. That avoids the classic TOCTOU
// race ("found free port → sidecar tries to bind → another proc grabbed it").
//
// This module instead provides:
//   * `parseListeningLine` — extracts the port from the sidecar's
//     `[sidecar] listening on http://host:port` banner.
//   * `waitForHealth`     — polls `/api/health/` until 200 or timeout.

import * as http from "http";

const LISTENING_RE = /\[sidecar\]\s+listening on\s+https?:\/\/[^:\s]+:(\d+)/i;

/** Parse a sidecar log line; return port if it matches, otherwise null. */
export function parseListeningLine(line: string): number | null {
  const match = line.match(LISTENING_RE);
  if (!match) return null;
  const port = Number.parseInt(match[1], 10);
  return Number.isFinite(port) && port > 0 ? port : null;
}

/**
 * Poll `http://127.0.0.1:<port>/api/health/` until it returns 2xx or
 * `timeoutMs` elapses. Resolves with nothing on success, rejects with
 * an Error on timeout.
 */
export async function waitForHealth(
  port: number,
  timeoutMs: number,
  intervalMs = 500,
  host = "127.0.0.1",
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown = null;
  while (Date.now() < deadline) {
    try {
      const ok = await pingHealth(host, port);
      if (ok) return;
    } catch (e) {
      lastErr = e;
    }
    await sleep(intervalMs);
  }
  throw new Error(
    `sidecar health check timed out after ${timeoutMs}ms` +
      (lastErr ? ` (last error: ${String(lastErr)})` : ""),
  );
}

function pingHealth(host: string, port: number): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host,
        port,
        path: "/api/health/",
        method: "GET",
        timeout: 2000,
      },
      (res) => {
        // Drain the response so the socket can be reused / closed cleanly.
        res.resume();
        const code = res.statusCode ?? 0;
        resolve(code >= 200 && code < 300);
      },
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy(new Error("health probe timeout"));
    });
    req.end();
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
