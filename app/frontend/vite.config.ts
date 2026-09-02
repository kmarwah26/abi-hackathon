import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served at the domain root on Databricks Apps, so base "/". In dev, proxy /api
// to the FastAPI server on :8000 (so we never ship CORS config).
export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
