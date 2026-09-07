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
        // 不做 rewrite：后端路由挂在 /api 前缀下（前端 axios baseURL 也是 /api），
        // 原样转发即可；此前剥掉前缀会被后端 SPA 兜底路由拦截返回 HTML。
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
