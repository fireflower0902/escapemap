// 남자 탐정 솔로 SVG — 검색 페이지용
// viewBox 0 0 235 370 으로 남자 탐정 부분만 표시

export default function DetectiveBoy({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 235 370"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="남자 탐정 캐릭터"
    >
      <defs>
        <radialGradient id="boy-skin" cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#FFF0E0" />
          <stop offset="100%" stopColor="#F5C8A0" />
        </radialGradient>
        <radialGradient id="boy-cape" cx="30%" cy="15%" r="80%">
          <stop offset="0%" stopColor="#3A3A3A" />
          <stop offset="100%" stopColor="#111111" />
        </radialGradient>
        <radialGradient id="boy-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FEF3C7" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#FEF3C7" stopOpacity="0" />
        </radialGradient>
      </defs>

      <ellipse cx="120" cy="185" rx="115" ry="160" fill="url(#boy-glow)" />
      <ellipse cx="138" cy="355" rx="58" ry="9" fill="#D97706" opacity="0.18" />

      {/* 망토 */}
      <path
        d="M83 228 Q88 315 90 348 L186 348 Q188 315 193 228
           Q175 242 138 244 Q101 242 83 228 Z"
        fill="url(#boy-cape)"
      />
      <path
        d="M88 218 Q100 235 138 238 Q176 235 188 218
           Q178 208 165 212 Q155 216 138 218 Q121 216 111 212 Q98 208 88 218 Z"
        fill="#2A2A2A"
      />
      <rect x="126" y="225" width="24" height="26" rx="4" fill="#F5F5F5" />
      <path d="M126 233 L132 237 L126 241 Z" fill="#111" />
      <path d="M150 233 L144 237 L150 241 Z" fill="#111" />
      <circle cx="138" cy="237" r="3.5" fill="#222" />

      {/* 다리 */}
      <rect x="112" y="325" width="22" height="30" rx="9" fill="#111" />
      <rect x="142" y="325" width="22" height="30" rx="9" fill="#111" />
      <ellipse cx="123" cy="354" rx="18" ry="7" fill="#0A0A0A" />
      <ellipse cx="153" cy="354" rx="18" ry="7" fill="#0A0A0A" />

      {/* 왼팔 — 돋보기 */}
      <path d="M90 230 Q62 262 46 288" stroke="#222" strokeWidth="24" strokeLinecap="round" fill="none" />
      <circle cx="46" cy="290" r="13" fill="url(#boy-skin)" />
      <circle cx="30" cy="308" r="24" fill="rgba(180,220,255,0.22)" stroke="#8B6914" strokeWidth="5.5" />
      <circle cx="30" cy="308" r="17" fill="rgba(200,235,255,0.12)" />
      <path d="M18 298 Q22 294 28 296" stroke="white" strokeWidth="2.5" strokeLinecap="round" opacity="0.7" />
      <line x1="48" y1="325" x2="62" y2="338" stroke="#7A5C10" strokeWidth="8" strokeLinecap="round" />

      {/* 오른팔 — 엄지 척 */}
      <path d="M186 230 Q210 252 214 272" stroke="#222" strokeWidth="22" strokeLinecap="round" fill="none" />
      <circle cx="212" cy="275" r="14" fill="url(#boy-skin)" />
      <path d="M206 268 Q204 258 210 255 Q218 254 218 262 Q218 268 214 272" fill="url(#boy-skin)" stroke="#E8C090" strokeWidth="1" />

      {/* 머리 */}
      <circle cx="138" cy="158" r="70" fill="url(#boy-skin)" />
      <path d="M95 140 Q110 108 138 102 Q166 108 181 140" fill="#1A1A1A" />
      <ellipse cx="80" cy="172" rx="13" ry="22" fill="#1A1A1A" />
      <ellipse cx="196" cy="172" rx="13" ry="22" fill="#1A1A1A" />

      {/* 셜록 모자 */}
      <path
        d="M78 152 Q100 142 138 140 Q176 142 198 152
           Q200 162 196 166 Q176 158 138 156 Q100 158 80 166 Q76 162 78 152 Z"
        fill="#2C2C2C"
      />
      <path d="M85 152 Q92 108 138 100 Q184 108 191 152 Z" fill="#222" />
      <path
        d="M90 148 Q108 130 138 126 Q168 130 186 148
           Q178 128 160 116 Q150 109 138 107 Q126 109 116 116 Q98 128 90 148 Z"
        fill="#2A2A2A"
      />
      <path d="M115 102 Q124 92 130 97 Q136 92 145 102 Q138 107 130 103 Q122 107 115 102 Z" fill="#111" />
      <circle cx="130" cy="100" r="4.5" fill="#1A1A1A" />

      {/* 볼 홍조 */}
      <ellipse cx="105" cy="174" rx="15" ry="10" fill="#FFB3A7" opacity="0.55" />
      <ellipse cx="171" cy="174" rx="15" ry="10" fill="#FFB3A7" opacity="0.55" />

      {/* 눈 */}
      <ellipse cx="118" cy="158" rx="14" ry="15" fill="white" />
      <circle cx="118" cy="160" r="9.5" fill="#201810" />
      <circle cx="122" cy="156" r="4" fill="white" />
      <circle cx="115" cy="163" r="1.8" fill="white" opacity="0.55" />
      <ellipse cx="158" cy="158" rx="14" ry="15" fill="white" />
      <circle cx="158" cy="160" r="9.5" fill="#201810" />
      <circle cx="162" cy="156" r="4" fill="white" />
      <circle cx="155" cy="163" r="1.8" fill="white" opacity="0.55" />

      {/* 눈썹 */}
      <path d="M105 142 Q118 136 131 141" stroke="#111" strokeWidth="3.5" strokeLinecap="round" fill="none" />
      <path d="M145 141 Q158 136 171 142" stroke="#111" strokeWidth="3.5" strokeLinecap="round" fill="none" />

      {/* 코 */}
      <ellipse cx="138" cy="173" rx="5.5" ry="3.8" fill="#F0A070" opacity="0.65" />

      {/* 입 */}
      <path d="M122 184 Q138 198 154 184" stroke="#C05838" strokeWidth="2.8" fill="none" strokeLinecap="round" />
      <path d="M124 184 Q138 194 152 184" fill="#E8907A" opacity="0.25" />

      <text x="192" y="80" fontSize="16" opacity="0.55">✨</text>
      <text x="15" y="88" fontSize="13" opacity="0.45">⭐</text>
    </svg>
  );
}
