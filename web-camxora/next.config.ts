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
  async redirects() {
    return [
      { source: "/terms", destination: "/legal#terms", permanent: false },
      { source: "/privacy", destination: "/legal#privacy", permanent: false },
      { source: "/cookies", destination: "/legal#cookies", permanent: false },
      { source: "/copyright", destination: "/legal#copyright", permanent: false },
      { source: "/acceptable-use", destination: "/legal#acceptable", permanent: false },
      { source: "/data-deletion", destination: "/legal#deletion", permanent: false },
    ];
  },
};

export default nextConfig;
