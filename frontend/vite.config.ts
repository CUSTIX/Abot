/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Only the one Node global this file needs (avoids pulling in all of @types/node).
declare const process: { env: Record<string, string | undefined> };

// Where /api is proxied in dev (docker compose sets API_URL=http://api:8000).
const apiUrl = process.env.API_URL ?? "http://localhost:8001";

// Dev: Vite serves the app on :5173 and proxies /api to Django, so the browser sees one origin
// (session cookie + CSRF work exactly as in production).
// Build: assets live under /static/ because Django (WhiteNoise) serves them in production.
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/" : "/",
  plugins: [react()],
  server: {
    port: 5173,
    // In Docker on Windows/macOS, file changes in a bind mount don't send events: poll instead.
    watch: process.env.VITE_POLL === "true" ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      "/api": { target: apiUrl },
      "/admin": { target: apiUrl },
    },
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
  test: { environment: "jsdom" },
}));
