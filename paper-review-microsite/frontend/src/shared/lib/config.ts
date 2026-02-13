/**
 * Application configuration from environment variables.
 */
export const config = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || "development",

  get apiUrl() {
    return `${this.apiBaseUrl}/api`;
  },

  get isProduction() {
    return this.environment === "production";
  },
};
