/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development, /api is proxied to the FastAPI backend, so no CORS setup is needed.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.MEETINGMIND_API_PROXY || "http://127.0.0.1:8000";
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: { "/api": { target, changeOrigin: true } },
      fs: { allow: [".."] }, // the sample transcript lives in ../samples
    },
    preview: { port: 4173, proxy: { "/api": { target, changeOrigin: true } } },
    test: { environment: "jsdom" },
  };
});
