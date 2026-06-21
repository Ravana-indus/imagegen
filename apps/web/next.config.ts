import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.API_ORIGIN || "http://127.0.0.1:8000"}/api/v1/:path*`,
      },
      {
        source: "/storage/:path*",
        destination: `${process.env.API_ORIGIN || "http://127.0.0.1:8000"}/storage/:path*`,
      },
    ];
  },
};

export default config;
