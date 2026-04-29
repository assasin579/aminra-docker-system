// Sentry init for the Vercel Edge runtime (middleware, edge routes).
// Even if we don't use Edge today, having the file prevents startup warnings.

import * as Sentry from "@sentry/nextjs";

const DSN = process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN;
const ENV =
  process.env.SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development";

if (DSN) {
  Sentry.init({
    dsn: DSN,
    environment: ENV,
    tracesSampleRate: ENV === "production" ? 0.25 : 1.0,
    sendDefaultPii: false,
    debug: false,
  });
}
