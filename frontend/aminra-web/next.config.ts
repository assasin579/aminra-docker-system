import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  reactCompiler: false,
  allowedDevOrigins: [
    "fe.silvergem.org",
    "localhost:3000",
    "dev-web.silvergem.org",
    "dev-api.silvergem.org",
  ],

  // Docker standalone output configuration
  output: "standalone",

  // Use empty turbopack config to silence Turbopack warnings
  turbopack: {},

  // Better chunk handling configuration
  experimental: {
    webpackBuildWorker: true,
  },
};

// Wrap with Sentry to upload sourcemaps + tunnel ad-blocker safe error reports.
// No-op if SENTRY_AUTH_TOKEN not set (dev/CI without Sentry org).
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT || "aminra-web",
  silent: true,
  widenClientFileUpload: true,
  sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN },
  disableLogger: true,
});
