import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 백엔드 API 주소 설정
  // 개발 중에는 localhost:8000, 배포 후에는 실제 서버 주소로 변경
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
