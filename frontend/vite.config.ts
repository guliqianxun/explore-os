import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite config for the explore-os frontend.
//   * dev server on 5173 (Electron main reads VITE_DEV_SERVER_URL to embed it)
//   * relative `base` so the file:// load in packaged Electron resolves assets
//   * `@/` -> `src/` for shadcn/ui-style imports
export default defineConfig({
  plugins: [react()],
  base: "./",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "127.0.0.1",   // 明确 IPv4，避免 Windows localhost 解析到 ::1 而 Electron 走 127.0.0.1
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
});
