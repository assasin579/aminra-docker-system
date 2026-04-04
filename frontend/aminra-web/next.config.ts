import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: false,
  allowedDevOrigins: ['fe.silvergem.org', 'localhost:3000'],
  
  // Docker standalone output configuration
  output: 'standalone',
  
  // Use empty turbopack config to silence Turbopack warnings
  turbopack: {},
  
  // Better chunk handling configuration
  experimental: {
    webpackBuildWorker: true,
  },
};

export default nextConfig;
