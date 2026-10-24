import type { NextConfig } from "next";

const backendUrl = process.env.PLATFORM_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: {
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/v3/:path*",
        destination: `${backendUrl}/api/v3/:path*`,
      },
    ];
  },
};

export default nextConfig;
