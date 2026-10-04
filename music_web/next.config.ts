import type { NextConfig } from 'next';
import path from 'path';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: {
    root: path.join(__dirname, '..'),
  },
  async headers() {
    return [
      {
        source: '/((?!_next/static|_next/image|favicon.ico).*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'private, no-cache, no-store, max-age=0, must-revalidate',
          },
        ],
      },
    ];
  },
  async rewrites() {
    // Local dev only: the browser calls same-origin /api/v3/* and production
    // routes it to the Platform API via the host/proxy. When running `next dev`
    // standalone there is no proxy, so forward to the local API instead.
    if (process.env.NODE_ENV !== 'development') return [];
    const backend = (process.env.PLATFORM_API_URL || 'http://localhost:8000').replace(/\/$/, '');
    return [
      { source: '/api/v3/:path*', destination: `${backend}/api/v3/:path*` },
    ];
  },
};

export default nextConfig;
