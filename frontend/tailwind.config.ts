import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // 브랜드 컬러 — 노란색 계열
        brand: {
          50:  "#FFFBEB",   // 배경용 아주 연한 노랑
          100: "#FEF3C7",   // 카드 배경용 연한 노랑
          200: "#FDE68A",   // 테두리용 노랑
          300: "#FCD34D",   // 기본 노랑
          400: "#FBBF24",   // 메인 포인트 컬러
          500: "#F59E0B",   // 버튼 호버
          600: "#D97706",   // 강조 텍스트
          700: "#B45309",   // 짙은 강조
        },
      },
      fontFamily: {
        sans: ["Pretendard", "Apple SD Gothic Neo", "sans-serif"],
      },
      animation: {
        "float": "float 3s ease-in-out infinite",
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
