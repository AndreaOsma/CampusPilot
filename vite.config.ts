import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
  // Solo los tests de la app: inbox-worker/ es otro paquete (Cloudflare) con sus propias
  // dependencias y sus tests (npm test dentro de esa carpeta).
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
