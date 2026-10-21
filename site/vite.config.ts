/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// O GitHub Pages serve o projeto em https://<usuario>.github.io/Radar-PNCP/
// (se o repositório mudar de nome ou ganhar domínio próprio: VITE_BASE=/ npm run build)
export default defineConfig(({ command, mode, isPreview }) => ({
  base:
    loadEnv(mode, ".", "VITE_").VITE_BASE ?? (command === "build" || isPreview ? "/Radar-PNCP/" : "/"),
  plugins: [react()],
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
}));
