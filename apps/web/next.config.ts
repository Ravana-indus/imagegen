import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    if (!process.env.API_ORIGIN) {
      return [];
    }
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.API_ORIGIN}/api/v1/:path*`,
      },
    ];
  },
};

export default config;
