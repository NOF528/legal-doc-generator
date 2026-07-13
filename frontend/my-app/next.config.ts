import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 开发时允许跨域请求到后端
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
