import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: "http://localhost:4003/:path*",
      },
    ];
  },
};

export default nextConfig;
