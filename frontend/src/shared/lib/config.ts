// Frontend configuration from environment variables

export const config = {
  // API Configuration
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",

  // Environment
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || "development",
  stripePublishableKey: process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "",
  minCredits: {
    conversation: Number(process.env.NEXT_PUBLIC_MIN_USER_CREDITS_FOR_CONVERSATION || "0"),
    researchPipeline: Number(process.env.NEXT_PUBLIC_MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE || "0"),
  },

  // Derived values
  get apiUrl() {
    return `${this.apiBaseUrl}/api`;
  },
} as const;

// Type-safe environment check
export const isDevelopment = config.environment === "development";
export const isProduction = config.environment === "production";

// Project constraints
export const constants = {
  MAX_PROJECT_TITLE_LENGTH: 80,
  POLL_INTERVAL_MS: 3000,
} as const;
