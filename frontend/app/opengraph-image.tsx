import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "이스케이프맵 — 방탈출 빈자리 실시간 검색";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          background: "linear-gradient(135deg, #1C1917 0%, #292524 60%, #1C1917 100%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          justifyContent: "center",
          padding: "80px 96px",
          fontFamily: "sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* 배경 원형 장식 */}
        <div
          style={{
            position: "absolute",
            right: -80,
            top: -80,
            width: 480,
            height: 480,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(251,191,36,0.12) 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 600,
            bottom: -60,
            width: 320,
            height: 320,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(251,191,36,0.07) 0%, transparent 70%)",
          }}
        />

        {/* 자물쇠 이모지 + 앱 이름 */}
        <div style={{ display: "flex", alignItems: "center", gap: 28, marginBottom: 32 }}>
          <div
            style={{
              width: 96,
              height: 96,
              background: "rgba(251,191,36,0.15)",
              borderRadius: 24,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 52,
              border: "2px solid rgba(251,191,36,0.3)",
            }}
          >
            🔐
          </div>
          <span
            style={{
              fontSize: 64,
              fontWeight: 900,
              color: "#FFFFFF",
              letterSpacing: "-1px",
            }}
          >
            이스케이프맵
          </span>
        </div>

        {/* 태그라인 */}
        <div
          style={{
            fontSize: 32,
            color: "#FBBF24",
            fontWeight: 700,
            marginBottom: 24,
            letterSpacing: "0.5px",
          }}
        >
          방탈출 빈자리 실시간 검색
        </div>

        {/* 설명 */}
        <div
          style={{
            fontSize: 24,
            color: "#A8A29E",
            fontWeight: 400,
            lineHeight: 1.5,
            maxWidth: 680,
          }}
        >
          전국 방탈출 카페 예약 현황을 한눈에 확인하고
          원하는 테마를 놓치지 마세요.
        </div>

        {/* 하단 태그 배지들 */}
        <div style={{ display: "flex", gap: 16, marginTop: 48 }}>
          {["강남/역삼", "홍대/합정", "잠실/송파", "부산", "+ 11개 지역"].map((label) => (
            <div
              key={label}
              style={{
                padding: "8px 20px",
                background: "rgba(255,255,255,0.07)",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.12)",
                color: "#D6D3D1",
                fontSize: 18,
                fontWeight: 500,
              }}
            >
              {label}
            </div>
          ))}
        </div>

        {/* 우측 대형 자물쇠 장식 */}
        <div
          style={{
            position: "absolute",
            right: 80,
            top: "50%",
            transform: "translateY(-50%)",
            fontSize: 240,
            opacity: 0.06,
          }}
        >
          🔐
        </div>
      </div>
    ),
    { ...size }
  );
}
