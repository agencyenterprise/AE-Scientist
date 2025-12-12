import nextConfig from "eslint-config-next";
import eslintConfigPrettier from "eslint-config-prettier";

const eslintConfig = [
  // Ignore patterns
  {
    ignores: [
      "build/",
      "node_modules/",
      ".next/",
      "*.config.js",
      "*.config.ts",
      "*.config.mjs",
      "coverage/",
      "public/",
      "src/types/api.gen.ts",
    ],
  },
  // Next.js config (includes React, React Hooks, TypeScript, jsx-a11y)
  ...nextConfig,
  // Prettier config (disables conflicting rules)
  eslintConfigPrettier,
  // Custom rules
  {
    rules: {
      // TypeScript enforcement
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/prefer-as-const": "error",

      // General code quality rules
      "no-console": "warn",
      "no-debugger": "error",
      "prefer-const": "error",
      "no-var": "error",
    },
  },
  // Prevent JavaScript files
  {
    files: ["**/*.js", "**/*.jsx"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Program",
          message:
            "JavaScript files are not allowed. Please use TypeScript (.ts/.tsx) files instead.",
        },
      ],
    },
  },
];

export default eslintConfig;