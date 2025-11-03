import { defineConfig } from "vitest/config"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    setupFiles: ["./tests/setup.ts"],
    include: ["lib/**/*.test.ts", "components/**/*.test.tsx", "components/**/__tests__/**/*.test.tsx"],
    alias: {
      "@": resolve(__dirname)
    },
    environmentMatchGlobs: [
      ["components/**/*.test.tsx", "jsdom"],
      ["components/**/__tests__/**/*.test.tsx", "jsdom"]
    ]
  }
})
