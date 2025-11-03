import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        status: {
          queued: "#1E3A8A",
          running: "#2563EB",
          auto: "#7C3AED",
          awaiting: "#F59E0B",
          success: "#10B981",
          failed: "#DC2626",
          canceled: "#6B7280"
        }
      }
    }
  },
  plugins: []
}

export default config
