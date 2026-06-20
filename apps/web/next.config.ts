import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    if (!process.env.API_ORIGIN) {
      return { fallback: [] };
    }
    return {
      fallback: [
        {
          source: "/api/v1/:path*",
          destination: `${process.env.API_ORIGIN}/api/v1/:path*`,
        },
        {
          source: "/storage/:path*",
          destination: `${process.env.API_ORIGIN}/storage/:path*`,
        },
      ],
    };
  },
};

export default config;
