// Sentry init for browser/client runtime.
// Auto-loaded by @sentry/nextjs at app boot.
//
// Sample rates:
//   dev   → 100% trace, 0% replay (verbose, no PII storage cost)
//   prod  → 25%  trace, 0% replay (raise as needed; replay needs consent)
//
// DSN sourced from NEXT_PUBLIC_SENTRY_DSN at build time. If absent, init is
// skipped (no errors leak; logging falls back to console).

import * as Sentry from "@sentry/nextjs";

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
const ENV =
  process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ||
  process.env.NODE_ENV ||
  "development";

if (DSN) {
  Sentry.init({
    dsn: DSN,
    environment: ENV,
    tracesSampleRate: ENV === "production" ? 0.25 : 1.0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    // Strip PII by default; opt-in via setUser() in auth flow if needed.
    sendDefaultPii: false,
    // Keep init non-blocking; failures here must not break boot.
    debug: false,
  });
}
