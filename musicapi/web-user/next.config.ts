import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:4003";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
