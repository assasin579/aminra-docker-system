import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: false,
  allowedDevOrigins: ['fe.silvergem.org', 'localhost:3000'],
  
  // Docker standalone output configuration
  output: 'standalone',
};

export default nextConfig;
