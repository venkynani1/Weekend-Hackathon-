import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        strictExecutionOrder: true,
        codeSplitting: {
          groups: [
            { name: "react", test: /node_modules[\\/](react|react-dom|react-router|react-router-dom)/, priority: 30 },
            { name: "supabase", test: /node_modules[\\/](@supabase|jose)/, priority: 25 },
            { name: "motion", test: /node_modules[\\/](motion|framer-motion)/, priority: 20 },
            { name: "query", test: /node_modules[\\/]@tanstack/, priority: 20 },
            { name: "icons", test: /node_modules[\\/]lucide-react/, priority: 15 },
            { name: "vendor", test: /node_modules/, maxSize: 240_000, priority: 5 },
          ],
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/downloads": "http://127.0.0.1:5000",
    },
  },
});
