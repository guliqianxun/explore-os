import axios, { AxiosInstance } from "axios";

// `window.explore` is exposed by Electron's preload (see electron/src/preload.ts).
// In a plain browser (web debug) it's undefined → fall back to 8000.
interface ExploreBridge {
  getBackendPort(): Promise<number | null>;
}

declare global {
  interface Window {
    explore?: ExploreBridge;
  }
}

const FALLBACK_PORT = 8000;

let cachedClient: AxiosInstance | null = null;
let cachedPort: number | null = null;

async function resolvePort(): Promise<number> {
  if (cachedPort !== null) return cachedPort;
  const bridge = window.explore;
  if (bridge && typeof bridge.getBackendPort === "function") {
    try {
      const p = await bridge.getBackendPort();
      if (typeof p === "number" && p > 0) {
        cachedPort = p;
        return p;
      }
    } catch {
      // fall through to fallback
    }
  }
  cachedPort = FALLBACK_PORT;
  return FALLBACK_PORT;
}

/** Returns a memoised axios instance pointed at the live sidecar. */
export async function getApi(): Promise<AxiosInstance> {
  if (cachedClient) return cachedClient;
  const port = await resolvePort();
  cachedClient = axios.create({
    baseURL: `http://127.0.0.1:${port}/api`,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
  });
  return cachedClient;
}
