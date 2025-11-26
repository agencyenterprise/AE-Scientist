import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/conversations/files/**',
      },
      {
        protocol: 'https',
        hostname: '*.railway.app',
        pathname: '/conversations/files/**',
      },
    ],
  },
};

export default nextConfig;
