import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, calls to /api and /health are forwarded to the Python backend.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
