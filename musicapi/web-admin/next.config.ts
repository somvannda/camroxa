import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
