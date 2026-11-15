import type { Metadata } from "next";
import "./globals.css";
import LegacyChrome from "@/components/teum/LegacyChrome";
import { AuthProvider } from "@/contexts/AuthContext";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://escapemap.reviewhyun.workers.dev"),
  title: "방픽 — 내 취향의 방탈출을 고르다",
  description:
    "전국 방탈출 카페와 수집한 예약 시간표를 한눈에. 일상에 작은 탈출을 만나보세요.",
  icons: {
    icon: [{url:"/brand/bangpick-favicon-v1.png",sizes:"64x64",type:"image/png"}],
    shortcut: "/brand/bangpick-favicon-v1.png",
    apple: [{url:"/brand/bangpick-apple-icon-v1.png",sizes:"180x180",type:"image/png"}],
  },
  twitter: {card:"summary_large_image",title:"방픽 — 내 취향의 방탈출을 고르다"},
  keywords: "방탈출, 예약, 빈자리, 강남, 홍대, 방탈출카페",
  openGraph: {
    title: "방픽 — 내 취향의 방탈출을 고르다",
    description: "전국 방탈출 카페와 실제 수집한 예약 시간표를 한눈에.",
    url: process.env.NEXT_PUBLIC_SITE_URL || "https://escapemap.reviewhyun.workers.dev",
    siteName: "방픽",
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
        <AuthProvider>
          <LegacyChrome>{children}</LegacyChrome>
        </AuthProvider>
      </body>
    </html>
  );
}
