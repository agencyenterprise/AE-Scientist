// This file configures the initialization of Sentry on the server.
// The config you add here will be used whenever the server handles a request.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: "https://b87a78265f78bb2542682116cdd9db29@o323538.ingest.us.sentry.io/4510521707069440",

  // Disable Sentry in development
  enabled: process.env.NODE_ENV !== "development",

  // Set environment from env var, fallback to NODE_ENV
  environment: process.env.SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development",

  // Define how likely traces are sampled. Adjust this value in production, or use tracesSampler for greater control.
  tracesSampleRate: 1,

  // Enable logs to be sent to Sentry
  enableLogs: true,

  // Enable sending user PII (Personally Identifiable Information)
  // https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/options/#sendDefaultPii
  sendDefaultPii: true,
});
