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
        // 브랜드 컬러 — 따뜻한 브론즈 계열
        brand: {
          50:  "#FAF5F0",   // 배경용 아주 연한 브라운
          100: "#F3EBE3",   // 카드 배경용 연한 브라운
          200: "#E8DED3",   // 테두리용 브라운
          300: "#D9C9B8",   // 중간 톤
          400: "#D4A574",   // 메인 포인트 컬러 (따뜻한 브론즈)
          500: "#C5955F",   // 버튼 호버
          600: "#A07D47",   // 강조 텍스트
          700: "#8B6B3F",   // 짙은 강조
        },
      },
      fontFamily: {
        sans: ["Pretendard", "Apple SD Gothic Neo", "sans-serif"],
      },
      animation: {
        "float": "float 3s ease-in-out infinite",
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.15s ease-out",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateX(-50%) translateY(4px)" },
          "100%": { opacity: "1", transform: "translateX(-50%) translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
