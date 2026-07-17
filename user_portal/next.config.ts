import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  devIndicators: false,
  turbopack: {
    root: path.join(__dirname, ".."),
  },
  async redirects() {
    return [
      {
        source: "/signup",
        destination: "/register",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
