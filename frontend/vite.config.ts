import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: true,
    port: 5173,
    allowedHosts: ["simplet.hamecte.ru", "localhost"],
    hmr: {
      host: "simplet.hamecte.ru",
      clientPort: 443,
      protocol: "wss",
    },
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
