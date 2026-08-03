import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("/@mui/") || id.includes("/mui-")) return "vendor-mui";
          if (id.includes("/@emotion/")) return "vendor-emotion";
          if (id.includes("/react/") || id.includes("/react-dom/") || id.includes("/scheduler/")) {
            return "vendor-react";
          }
          if (id.includes("/@tanstack/")) return "vendor-tanstack";
          if (id.includes("/react-hook-form/") || id.includes("/@hookform/") || id.includes("/zod/")) {
            return "vendor-forms";
          }
          return "vendor-misc";
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});
