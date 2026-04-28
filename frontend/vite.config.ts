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
    // ft-029: manualChunks ensures the pdf.js + react-pdf bundles end up in a
    // dedicated chunk so the main app shell doesn't pay their ~600KB cost
    // until the user opens a paper with a PDF. The dynamic `import()` in
    // ReadingStation already triggers a split, but this tightens the cut.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/pdfjs-dist")) return "pdfjs";
          if (id.includes("node_modules/react-pdf")) return "pdfjs";
          return undefined;
        },
      },
    },
  },
  // pdfjs-dist 4.x ships ESM workers with `import.meta.url` — Vite needs to
  // know to optimize-include them so dev-mode prebundle doesn't trip.
  optimizeDeps: {
    include: ["react-pdf", "pdfjs-dist"],
  },
});
