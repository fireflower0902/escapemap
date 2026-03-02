// 여자 탐정 솔로 SVG — CTA 배너용
// viewBox "200 0 240 370" 으로 여자 탐정 부분만 크롭해서 표시

export default function DetectiveGirl({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="200 0 240 370"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="여자 탐정 캐릭터"
    >
      <defs>
        <radialGradient id="girl-skin" cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#FFF0E0" />
          <stop offset="100%" stopColor="#F5C8A0" />
        </radialGradient>
        <radialGradient id="girl-coat" cx="30%" cy="20%" r="75%">
          <stop offset="0%" stopColor="#D8C8A8" />
          <stop offset="100%" stopColor="#B8A888" />
        </radialGradient>
        <radialGradient id="girl-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FEF3C7" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#FEF3C7" stopOpacity="0" />
        </radialGradient>
      </defs>

      <ellipse cx="302" cy="185" rx="130" ry="160" fill="url(#girl-glow)" />
      <ellipse cx="302" cy="355" rx="60" ry="9" fill="#D97706" opacity="0.18" />

      {/* 긴 머리카락 뒤 */}
      <path d="M248 222 Q240 290 244 348" stroke="#1A1A1A" strokeWidth="36" strokeLinecap="round" fill="none" />
      <path d="M356 222 Q364 290 360 348" stroke="#1A1A1A" strokeWidth="30" strokeLinecap="round" fill="none" />

      {/* 코트 */}
      <path
        d="M248 228 Q253 315 255 348 L349 348 Q351 315 356 228
           Q340 244 302 246 Q264 244 248 228 Z"
        fill="url(#girl-coat)"
      />
      <path
        d="M252 218 Q265 232 302 228 Q339 232 352 218
           Q344 208 332 213 Q320 218 302 220 Q284 218 272 213 Q260 208 252 218 Z"
        fill="#C0B090"
      />
      <line x1="302" y1="220" x2="302" y2="330" stroke="#A09070" strokeWidth="2" />

      {/* 빨간 단추 */}
      {[238, 258, 278, 298].map((y, i) => (
        <g key={i}>
          <circle cx="292" cy={y} r="7" fill="#BB1800" />
          <circle cx="292" cy={y} r="5" fill="#CC2200" />
          <circle cx="290" cy={y - 2} r="2.2" fill="#FF5533" opacity="0.7" />
        </g>
      ))}

      {/* 줄무늬 셔츠 */}
      <rect x="295" y="218" width="14" height="28" fill="#EEE" rx="2" />
      {[222, 228, 234, 240].map((y, i) => (
        <line key={i} x1="295" y1={y} x2="309" y2={y} stroke="#3355AA" strokeWidth="2" />
      ))}

      {/* 쌍안경 */}
      <path d="M272 246 Q302 258 332 246" stroke="#CC2200" strokeWidth="3.5" fill="none" />
      <rect x="272" y="254" width="20" height="14" rx="4" fill="#2A2A2A" />
      <circle cx="282" cy="261" r="5.5" fill="#111" stroke="#555" strokeWidth="1.5" />
      <circle cx="282" cy="261" r="3.5" fill="#1A2240" />
      <circle cx="280" cy="259" r="1.5" fill="white" opacity="0.5" />
      <rect x="312" y="254" width="20" height="14" rx="4" fill="#2A2A2A" />
      <circle cx="322" cy="261" r="5.5" fill="#111" stroke="#555" strokeWidth="1.5" />
      <circle cx="322" cy="261" r="3.5" fill="#1A2240" />
      <circle cx="320" cy="259" r="1.5" fill="white" opacity="0.5" />
      <rect x="291" y="258" width="12" height="6" rx="2" fill="#383838" />

      {/* 다리 */}
      <rect x="272" y="325" width="22" height="30" rx="9" fill="#A89870" />
      <rect x="308" y="325" width="22" height="30" rx="9" fill="#A89870" />
      <ellipse cx="283" cy="354" rx="18" ry="7" fill="#7A6042" />
      <ellipse cx="319" cy="354" rx="18" ry="7" fill="#7A6042" />

      {/* 왼팔 — 손전등 */}
      <path d="M252 236 Q226 262 216 284" stroke="#B8A880" strokeWidth="22" strokeLinecap="round" fill="none" />
      <circle cx="214" cy="287" r="13" fill="url(#girl-skin)" />
      <rect x="202" y="284" width="14" height="26" rx="5" fill="#888" />
      <ellipse cx="209" cy="284" rx="9" ry="6" fill="#AAA" />
      <ellipse cx="209" cy="283" rx="6" ry="4" fill="#FFE566" opacity="0.85" />
      <path d="M200 278 Q209 270 218 278" stroke="#FFE566" strokeWidth="1.5" fill="none" opacity="0.6" />

      {/* 오른팔 — V 사인 */}
      <path d="M352 236 Q374 256 378 272" stroke="#B8A880" strokeWidth="22" strokeLinecap="round" fill="none" />
      <circle cx="377" cy="276" r="13" fill="url(#girl-skin)" />
      <path d="M373 272 Q371 258 376 250" stroke="url(#girl-skin)" strokeWidth="9" strokeLinecap="round" fill="none" />
      <path d="M376 250 Q378 244 381 248" stroke="#F5C8A0" strokeWidth="3" strokeLinecap="round" fill="none" />
      <path d="M381 273 Q381 259 384 251" stroke="url(#girl-skin)" strokeWidth="9" strokeLinecap="round" fill="none" />
      <path d="M384 251 Q386 245 389 249" stroke="#F5C8A0" strokeWidth="3" strokeLinecap="round" fill="none" />

      {/* 머리 */}
      <circle cx="302" cy="155" r="72" fill="url(#girl-skin)" />
      <path d="M244 163 Q252 115 302 108 Q352 115 360 163 Q350 138 302 133 Q254 138 244 163 Z" fill="#1A1A1A" />
      <path d="M253 145 Q264 128 278 132 Q265 136 260 148 Z" fill="#111" />

      {/* 플랫캡 */}
      <path d="M246 148 Q256 105 302 100 Q348 105 358 148 Z" fill="#888" />
      <path
        d="M246 148 Q268 140 302 138 Q336 140 358 148
           Q350 155 302 153 Q254 155 246 148 Z"
        fill="#999"
      />
      <path d="M246 148 Q256 142 268 145 Q263 157 249 159 Q243 154 246 148 Z" fill="#777" />
      <circle cx="302" cy="104" r="5.5" fill="#666" />
      <path d="M258 130 Q278 120 302 118" stroke="#777" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      <path d="M270 140 Q284 132 302 130" stroke="#777" strokeWidth="1.8" fill="none" strokeLinecap="round" />

      {/* 볼 홍조 */}
      <ellipse cx="268" cy="170" rx="17" ry="11" fill="#FFB3A7" opacity="0.65" />
      <ellipse cx="336" cy="170" rx="17" ry="11" fill="#FFB3A7" opacity="0.65" />

      {/* 주근깨 */}
      {[[266, 167], [273, 173], [260, 173]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.2" fill="#E8907A" opacity="0.48" />
      ))}

      {/* 눈 왼쪽 */}
      <ellipse cx="280" cy="156" rx="15" ry="16" fill="white" />
      <circle cx="280" cy="158" r="10" fill="#201810" />
      <circle cx="284" cy="154" r="4.2" fill="white" />
      <circle cx="277" cy="162" r="1.8" fill="white" opacity="0.55" />
      {[[267, 145, 270, 140], [273, 143, 274, 137], [280, 141, 281, 136], [287, 143, 289, 137], [293, 145, 297, 141]].map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#111" strokeWidth="2.2" strokeLinecap="round" />
      ))}

      {/* 눈 오른쪽 */}
      <ellipse cx="324" cy="156" rx="15" ry="16" fill="white" />
      <circle cx="324" cy="158" r="10" fill="#201810" />
      <circle cx="328" cy="154" r="4.2" fill="white" />
      <circle cx="321" cy="162" r="1.8" fill="white" opacity="0.55" />
      {[[311, 145, 308, 140], [317, 143, 316, 137], [323, 141, 323, 136], [329, 143, 331, 137], [335, 146, 338, 142]].map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#111" strokeWidth="2.2" strokeLinecap="round" />
      ))}

      {/* 눈썹 */}
      <path d="M268 140 Q280 133 292 139" stroke="#111" strokeWidth="2.8" strokeLinecap="round" fill="none" />
      <path d="M312 139 Q324 133 336 140" stroke="#111" strokeWidth="2.8" strokeLinecap="round" fill="none" />

      {/* 코 */}
      <ellipse cx="302" cy="172" rx="5.5" ry="3.8" fill="#F0A070" opacity="0.6" />

      {/* 입 */}
      <path d="M286 184 Q302 198 318 184" stroke="#C05838" strokeWidth="2.8" fill="none" strokeLinecap="round" />
      <path d="M288 184 Q302 196 316 184" fill="#E8907A" opacity="0.3" />

      <text x="400" y="78" fontSize="18" opacity="0.6">✨</text>
      <text x="215" y="42" fontSize="12" opacity="0.45">✦</text>
    </svg>
  );
}
