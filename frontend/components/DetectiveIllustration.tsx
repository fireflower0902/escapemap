// 귀여운 탐정 캐릭터 SVG 일러스트레이션
// 방탈출 테마에 맞춰 자물쇠와 돋보기를 들고 있는 탐정 캐릭터

export default function DetectiveIllustration({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 280 320"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="귀여운 탐정 캐릭터"
    >
      {/* ── 배경 원 (노란빛 후광) ─────────────── */}
      <circle cx="140" cy="160" r="130" fill="#FEF3C7" opacity="0.6" />
      <circle cx="140" cy="160" r="105" fill="#FDE68A" opacity="0.4" />

      {/* ── 그림자 ─────────────────────────────── */}
      <ellipse cx="140" cy="295" rx="65" ry="12" fill="#D97706" opacity="0.15" />

      {/* ── 탐정 모자 챙 ───────────────────────── */}
      <ellipse cx="140" cy="82" rx="62" ry="12" fill="#1C1917" />

      {/* ── 탐정 모자 본체 ─────────────────────── */}
      <rect x="90" y="35" width="100" height="52" rx="10" fill="#292524" />

      {/* ── 모자 리본 (노란색) ──────────────────── */}
      <rect x="90" y="72" width="100" height="10" rx="2" fill="#FBBF24" />

      {/* ── 얼굴 (동그란 원) ───────────────────── */}
      <circle cx="140" cy="140" r="55" fill="#FEF9C3" />
      <circle cx="140" cy="140" r="55" stroke="#FCD34D" strokeWidth="2" />

      {/* ── 볼 (귀여운 홍조) ───────────────────── */}
      <ellipse cx="112" cy="152" rx="10" ry="7" fill="#FCA5A5" opacity="0.5" />
      <ellipse cx="168" cy="152" rx="10" ry="7" fill="#FCA5A5" opacity="0.5" />

      {/* ── 눈 (왼쪽) ──────────────────────────── */}
      <circle cx="122" cy="132" r="8" fill="white" />
      <circle cx="122" cy="132" r="5" fill="#292524" />
      <circle cx="124" cy="130" r="1.5" fill="white" />

      {/* ── 눈 (오른쪽) ─────────────────────────── */}
      <circle cx="158" cy="132" r="8" fill="white" />
      <circle cx="158" cy="132" r="5" fill="#292524" />
      <circle cx="160" cy="130" r="1.5" fill="white" />

      {/* ── 모노클 (오른쪽 눈에) ──────────────────── */}
      <circle cx="158" cy="132" r="13" stroke="#D97706" strokeWidth="2.5" fill="none" />
      {/* 모노클 줄 */}
      <path d="M168 140 Q172 148 168 155" stroke="#D97706" strokeWidth="1.5" strokeLinecap="round" />

      {/* ── 코 ─────────────────────────────────── */}
      <ellipse cx="140" cy="148" rx="5" ry="3.5" fill="#FCD34D" />

      {/* ── 입 (귀여운 미소) ───────────────────── */}
      <path
        d="M126 162 Q140 174 154 162"
        stroke="#D97706"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />

      {/* ── 몸통 (코트) ────────────────────────── */}
      <rect x="92" y="188" width="96" height="85" rx="18" fill="#292524" />

      {/* ── 코트 깃 (노란색 넥타이) ────────────── */}
      <polygon points="140,192 150,210 140,228 130,210" fill="#FBBF24" />

      {/* ── 왼팔 (돋보기 들고 있음) ────────────── */}
      <path
        d="M92 210 Q60 220 45 240"
        stroke="#292524"
        strokeWidth="20"
        strokeLinecap="round"
      />
      {/* 돋보기 렌즈 */}
      <circle cx="38" cy="250" r="22" fill="rgba(251,191,36,0.25)" stroke="#D97706" strokeWidth="4" />
      <circle cx="38" cy="250" r="16" fill="rgba(251,191,36,0.1)" />
      {/* 돋보기 안에 자물쇠 (작은) */}
      <text x="30" y="257" fontSize="16" fill="#D97706">🔐</text>
      {/* 돋보기 손잡이 */}
      <line x1="54" y1="266" x2="68" y2="280" stroke="#D97706" strokeWidth="6" strokeLinecap="round" />

      {/* ── 오른팔 ─────────────────────────────── */}
      <path
        d="M188 210 Q215 220 225 238"
        stroke="#292524"
        strokeWidth="20"
        strokeLinecap="round"
      />
      {/* 오른손에 열쇠 */}
      <text x="215" y="252" fontSize="22">🗝️</text>

      {/* ── 다리 (왼쪽) ─────────────────────────── */}
      <rect x="106" y="265" width="26" height="35" rx="10" fill="#292524" />
      {/* 왼쪽 신발 */}
      <ellipse cx="119" cy="298" rx="20" ry="8" fill="#1C1917" />

      {/* ── 다리 (오른쪽) ────────────────────────── */}
      <rect x="148" y="265" width="26" height="35" rx="10" fill="#292524" />
      {/* 오른쪽 신발 */}
      <ellipse cx="161" cy="298" rx="20" ry="8" fill="#1C1917" />

      {/* ── 장식 별/반짝임 ──────────────────────── */}
      <text x="210" y="100" fontSize="18" opacity="0.6">✨</text>
      <text x="45" y="110" fontSize="14" opacity="0.5">⭐</text>
      <text x="230" y="170" fontSize="12" opacity="0.4">✦</text>
    </svg>
  );
}
