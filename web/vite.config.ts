import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      // noVNC 可视化人工接管（§25 方案 A：Web 内嵌 iframe）
      "/vnc": {
        target: "http://127.0.0.1:6080",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/vnc/, ""),
      },
    },
  },
});
