// 방탈출 탐험가 SVG — 픽사 스타일
// 헤드램프 + 황금 열쇠 + 손전등 소품
// viewBox 0 0 240 370

export default function EscapeExplorer({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 240 370"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="방탈출 탐험가 캐릭터"
    >
      <defs>
        <radialGradient id="ee-skin" cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#FFE4C4" />
          <stop offset="100%" stopColor="#FFBA80" />
        </radialGradient>
        <radialGradient id="ee-jacket" cx="30%" cy="18%" r="78%">
          <stop offset="0%" stopColor="#A08B5A" />
          <stop offset="100%" stopColor="#6B5530" />
        </radialGradient>
        <radialGradient id="ee-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FFF8E7" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#FFF8E7" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="ee-eye-l" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#4CAF50" />
          <stop offset="100%" stopColor="#2E7A32" />
        </radialGradient>
        <radialGradient id="ee-eye-r" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#4CAF50" />
          <stop offset="100%" stopColor="#2E7A32" />
        </radialGradient>
      </defs>

      {/* 배경 글로우 */}
      <ellipse cx="120" cy="185" rx="112" ry="158" fill="url(#ee-glow)" />
      {/* 그림자 */}
      <ellipse cx="122" cy="354" rx="54" ry="8" fill="#B8860B" opacity="0.2" />

      {/* ── 다리 ── */}
      <rect x="92" y="308" width="24" height="44" rx="11" fill="#3A3A5C" />
      <rect x="126" y="308" width="24" height="44" rx="11" fill="#3A3A5C" />
      {/* 신발 */}
      <ellipse cx="104" cy="351" rx="21" ry="8" fill="#1A1A2E" />
      <ellipse cx="138" cy="351" rx="21" ry="8" fill="#1A1A2E" />
      <path d="M88 347 Q104 343 120 347" stroke="#2A2A42" strokeWidth="2" strokeLinecap="round" />
      <path d="M122 347 Q138 343 154 347" stroke="#2A2A42" strokeWidth="2" strokeLinecap="round" />

      {/* ── 몸통 (탐험가 재킷) ── */}
      <path
        d="M76 220 Q76 308 83 320 L161 320 Q168 308 168 220
           Q156 234 121 236 Q86 234 76 220 Z"
        fill="url(#ee-jacket)"
      />
      {/* 재킷 깃 */}
      <path d="M121 220 L99 248 L121 240 L143 248 Z" fill="#5A4020" />
      {/* 가슴 포켓 */}
      <rect x="128" y="252" width="22" height="18" rx="4" fill="#5A4020" />
      <line x1="128" y1="258" x2="150" y2="258" stroke="#7A5828" strokeWidth="1.5" />
      {/* 어깨 패드 */}
      <ellipse cx="83" cy="226" rx="14" ry="8" fill="#8A7248" />
      <ellipse cx="159" cy="226" rx="14" ry="8" fill="#8A7248" />
      {/* 벨트 */}
      <rect x="76" y="291" width="92" height="13" rx="5" fill="#4A3418" />
      {/* 벨트 버클 */}
      <rect x="108" y="289" width="28" height="17" rx="4" fill="#8B6914" />
      <rect x="113" y="293" width="18" height="9" rx="2" fill="#6B5010" />
      <circle cx="122" cy="297" r="4" fill="#FFD700" />
      <circle cx="88" cy="297" r="3.5" fill="#6B5010" />
      <circle cx="156" cy="297" r="3.5" fill="#6B5010" />

      {/* ── 왼팔 (손전등) ── */}
      <path d="M80 232 Q50 264 36 288" stroke="#A08B5A" strokeWidth="24" strokeLinecap="round" fill="none" />
      <path d="M80 232 Q50 264 36 288" stroke="#8B7040" strokeWidth="18" strokeLinecap="round" fill="none" />
      {/* 손 */}
      <circle cx="38" cy="290" r="14" fill="url(#ee-skin)" />
      {/* 손전등 몸통 */}
      <rect x="10" y="280" width="16" height="46" rx="7" fill="#3A3A4A" />
      <rect x="8" y="274" width="20" height="13" rx="5" fill="#4A4A5A" />
      {/* 렌즈 */}
      <ellipse cx="18" cy="274" rx="10" ry="6.5" fill="#FFE566" opacity="0.9" />
      <ellipse cx="18" cy="274" rx="6" ry="4" fill="white" opacity="0.6" />
      {/* 빛 줄기 */}
      <path d="M8 272 L-2 250" stroke="#FFE566" strokeWidth="2.5" strokeLinecap="round" opacity="0.45" />
      <path d="M18 267 L16 244" stroke="#FFE566" strokeWidth="2.5" strokeLinecap="round" opacity="0.45" />
      <path d="M28 272 L38 250" stroke="#FFE566" strokeWidth="2.5" strokeLinecap="round" opacity="0.45" />
      {/* 버튼 + 그립 */}
      <circle cx="18" cy="302" r="4" fill="#2A2A3A" />
      <circle cx="18" cy="314" r="3" fill="#2A2A3A" />
      <line x1="10" y1="290" x2="26" y2="290" stroke="#2A2A3A" strokeWidth="1.5" opacity="0.5" />
      <line x1="10" y1="296" x2="26" y2="296" stroke="#2A2A3A" strokeWidth="1.5" opacity="0.5" />

      {/* ── 오른팔 (황금 열쇠) ── */}
      <path d="M164 232 Q194 260 210 280" stroke="#A08B5A" strokeWidth="24" strokeLinecap="round" fill="none" />
      <path d="M164 232 Q194 260 210 280" stroke="#8B7040" strokeWidth="18" strokeLinecap="round" fill="none" />
      {/* 손 */}
      <circle cx="212" cy="282" r="14" fill="url(#ee-skin)" />
      {/* 열쇠 링 */}
      <circle cx="226" cy="257" r="20" fill="none" stroke="#FFD700" strokeWidth="6.5" />
      <circle cx="226" cy="257" r="10" fill="none" stroke="#FFD700" strokeWidth="4.5" />
      <circle cx="226" cy="257" r="4.5" fill="#FFD700" />
      <circle cx="218" cy="249" r="4" fill="#FFD700" opacity="0.6" />
      <circle cx="234" cy="249" r="4" fill="#FFD700" opacity="0.6" />
      {/* 열쇠 기둥 */}
      <line x1="240" y1="270" x2="240" y2="322" stroke="#FFD700" strokeWidth="7" strokeLinecap="round" />
      {/* 열쇠 이빨 */}
      <line x1="240" y1="292" x2="228" y2="292" stroke="#FFD700" strokeWidth="6.5" strokeLinecap="round" />
      <line x1="240" y1="304" x2="232" y2="304" stroke="#FFD700" strokeWidth="6.5" strokeLinecap="round" />
      <line x1="240" y1="316" x2="230" y2="316" stroke="#FFD700" strokeWidth="5.5" strokeLinecap="round" />

      {/* ── 머리 ── */}
      <circle cx="121" cy="145" r="70" fill="url(#ee-skin)" />

      {/* 머리카락 */}
      <path
        d="M63 125 Q80 72 121 66 Q162 72 179 125
           Q172 98 157 86 Q142 76 121 74 Q100 76 85 86 Q70 98 63 125 Z"
        fill="#2A1A0C"
      />
      <ellipse cx="62" cy="150" rx="14" ry="23" fill="#2A1A0C" />
      <ellipse cx="180" cy="150" rx="14" ry="23" fill="#2A1A0C" />
      <path d="M96 80 Q121 70 142 80" stroke="#4A3020" strokeWidth="3.5" strokeLinecap="round" fill="none" opacity="0.55" />

      {/* ── 헤드램프 ── */}
      {/* 스트랩 */}
      <path d="M62 132 Q88 116 104 122" stroke="#3A3A4A" strokeWidth="5.5" strokeLinecap="round" fill="none" />
      <path d="M180 132 Q154 116 138 122" stroke="#3A3A4A" strokeWidth="5.5" strokeLinecap="round" fill="none" />
      {/* 램프 하우징 */}
      <rect x="100" y="113" width="42" height="20" rx="10" fill="#4A4A5A" />
      <rect x="103" y="116" width="36" height="14" rx="7" fill="#5A5A6A" />
      {/* 렌즈 */}
      <ellipse cx="121" cy="123" rx="13" ry="9" fill="#FFE566" opacity="0.88" />
      <ellipse cx="121" cy="123" rx="8" ry="5.5" fill="white" opacity="0.55" />
      {/* 헤드램프 빛 줄기 */}
      <path d="M108 113 L102 96" stroke="#FFE566" strokeWidth="2" strokeLinecap="round" opacity="0.4" />
      <path d="M121 111 L121 92" stroke="#FFE566" strokeWidth="2.5" strokeLinecap="round" opacity="0.4" />
      <path d="M134 113 L140 96" stroke="#FFE566" strokeWidth="2" strokeLinecap="round" opacity="0.4" />

      {/* 볼 홍조 */}
      <ellipse cx="88" cy="167" rx="19" ry="13" fill="#FFB3A7" opacity="0.48" />
      <ellipse cx="154" cy="167" rx="19" ry="13" fill="#FFB3A7" opacity="0.48" />

      {/* ── 눈 (픽사 스타일) ── */}
      {/* 왼쪽 */}
      <ellipse cx="102" cy="150" rx="18" ry="20" fill="white" />
      <circle cx="102" cy="152" r="13" fill="url(#ee-eye-l)" />
      <circle cx="102" cy="152" r="8.5" fill="#181010" />
      <circle cx="108" cy="145" r="5.5" fill="white" />
      <circle cx="98" cy="157" r="2.2" fill="white" opacity="0.45" />
      {/* 오른쪽 */}
      <ellipse cx="140" cy="150" rx="18" ry="20" fill="white" />
      <circle cx="140" cy="152" r="13" fill="url(#ee-eye-r)" />
      <circle cx="140" cy="152" r="8.5" fill="#181010" />
      <circle cx="146" cy="145" r="5.5" fill="white" />
      <circle cx="136" cy="157" r="2.2" fill="white" opacity="0.45" />

      {/* 눈썹 */}
      <path d="M86 131 Q102 123 118 130" stroke="#2A1A0C" strokeWidth="5" strokeLinecap="round" fill="none" />
      <path d="M124 130 Q140 123 156 131" stroke="#2A1A0C" strokeWidth="5" strokeLinecap="round" fill="none" />

      {/* 코 */}
      <path d="M115 172 Q121 178 127 172" stroke="#D08060" strokeWidth="2.8" strokeLinecap="round" fill="none" />

      {/* 입 (넓은 미소) */}
      <path d="M102 184 Q121 203 140 184" stroke="#C04830" strokeWidth="3.8" fill="none" strokeLinecap="round" />
      <path d="M104 185 Q121 199 138 185" fill="#E8857A" opacity="0.32" />
      {/* 보조개 */}
      <circle cx="101" cy="184" r="3.5" fill="#FFB3A7" opacity="0.55" />
      <circle cx="141" cy="184" r="3.5" fill="#FFB3A7" opacity="0.55" />

      {/* 반짝임 */}
      <path
        d="M196 68 L198 60 L200 68 L208 70 L200 72 L198 80 L196 72 L188 70 Z"
        fill="#FFD700" opacity="0.7"
      />
      <path
        d="M22 82 L23.5 76 L25 82 L31 83.5 L25 85 L23.5 91 L22 85 L16 83.5 Z"
        fill="#FFD700" opacity="0.5"
      />
      <circle cx="205" cy="98" r="3.5" fill="#FFE566" opacity="0.5" />
      <circle cx="18" cy="108" r="2.5" fill="#FFE566" opacity="0.4" />
    </svg>
  );
}
