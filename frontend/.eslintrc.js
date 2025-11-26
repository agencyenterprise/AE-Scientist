module.exports = {
  extends: [
    "next/core-web-vitals",
    "next/typescript",
    "prettier"
  ],
  plugins: ["prettier", "@typescript-eslint"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: {
      jsx: true,
    },
  },
  rules: {
    // TypeScript enforcement (basic rules that don't require type info)
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/no-non-null-assertion": "error",
    "@typescript-eslint/prefer-as-const": "error",

    // Additional TypeScript rules

    // General code quality rules
    "no-console": "warn",
    "no-debugger": "error",
    "prefer-const": "error",
    "no-var": "error",

    // Prettier integration
    "prettier/prettier": "error",
  },
  overrides: [
    {
      // Prevent JavaScript files from being used
      files: ["**/*.js", "**/*.jsx"],
      rules: {
        "no-restricted-syntax": [
          "error",
          {
            selector: "Program",
            message: "JavaScript files are not allowed. Please use TypeScript (.ts/.tsx) files instead.",
          },
        ],
      },
    },
  ],
  ignorePatterns: [
    "build/",
    "node_modules/",
    ".next/",
    "*.config.js",
    "*.config.ts", 
    "*.config.mjs",
    "coverage/",
    "public/",
    "src/types/api.gen.ts"
  ],
};