import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.VITE_DEV_API || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/v1": api,
      "/healthz": api,
    },
  },
});
