import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "이스케이프맵 — 방탈출 예약 통합 플랫폼",
  description:
    "전국 방탈출 카페 예약 가능 현황을 한눈에! 빈자리 알림으로 원하는 테마를 놓치지 마세요.",
  keywords: "방탈출, 예약, 빈자리, 강남, 홍대, 방탈출카페",
  openGraph: {
    title: "이스케이프맵 — 방탈출 빈자리 실시간 검색",
    description: "전국 방탈출 카페 예약 현황을 한눈에! 빈자리 알림으로 원하는 테마를 놓치지 마세요.",
    url: "https://escapemap-three.vercel.app",
    siteName: "이스케이프맵",
    locale: "ko_KR",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
