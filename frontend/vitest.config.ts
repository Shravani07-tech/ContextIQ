import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

// Vitest + React Testing Library config. tsconfigPaths reads the
// same "@/*" alias tsconfig.json already defines, so test imports
// don't need a second, hand-maintained alias map.
export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    css: false,
  },
});
