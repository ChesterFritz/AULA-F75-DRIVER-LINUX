import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";

// Builds straight into ../static, which server.py serves.
export default defineConfig({
  base: "./",
  plugins: [tailwindcss(), svelte()],
  build: { outDir: "../static", emptyOutDir: true, assetsInlineLimit: 0 },
});
