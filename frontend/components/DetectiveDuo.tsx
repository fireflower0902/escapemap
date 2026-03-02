// 귀여운 탐정 듀오 SVG 캐릭터
// 남자 탐정: 검정 셜록 망토 + 사슴가죽 모자 + 돋보기
// 여자 탐정: 베이지 트렌치코트 + 빨간 단추 + 쌍안경 + 플랫캡

export default function DetectiveDuo({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 440 370"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="귀여운 탐정 남녀 캐릭터"
    >
      <defs>
        <radialGradient id="duo-skin" cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#FFF0E0" />
          <stop offset="100%" stopColor="#F5C8A0" />
        </radialGradient>
        <radialGradient id="duo-cape" cx="30%" cy="15%" r="80%">
          <stop offset="0%" stopColor="#3A3A3A" />
          <stop offset="100%" stopColor="#111111" />
        </radialGradient>
        <radialGradient id="duo-coat" cx="30%" cy="20%" r="75%">
          <stop offset="0%" stopColor="#D8C8A8" />
          <stop offset="100%" stopColor="#B8A888" />
        </radialGradient>
        <radialGradient id="duo-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FEF3C7" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#FEF3C7" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* 배경 빛 */}
      <ellipse cx="220" cy="185" rx="200" ry="170" fill="url(#duo-glow)" />

      {/* ══════════════════════════════════════════
          남자 탐정 (왼쪽) — 검정 셜록 스타일
          ══════════════════════════════════════════ */}

      <ellipse cx="138" cy="355" rx="58" ry="9" fill="#D97706" opacity="0.18" />

      {/* 망토 본체 */}
      <path
        d="M83 228 Q88 315 90 348 L186 348 Q188 315 193 228
           Q175 242 138 244 Q101 242 83 228 Z"
        fill="url(#duo-cape)"
      />
      {/* 망토 어깨/칼라 */}
      <path
        d="M88 218 Q100 235 138 238 Q176 235 188 218
           Q178 208 165 212 Q155 216 138 218 Q121 216 111 212 Q98 208 88 218 Z"
        fill="#2A2A2A"
      />
      {/* 흰 셔츠 & 보타이 */}
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
      <circle cx="46" cy="290" r="13" fill="url(#duo-skin)" />
      <circle cx="30" cy="308" r="24" fill="rgba(180,220,255,0.22)" stroke="#8B6914" strokeWidth="5.5" />
      <circle cx="30" cy="308" r="17" fill="rgba(200,235,255,0.12)" />
      <path d="M18 298 Q22 294 28 296" stroke="white" strokeWidth="2.5" strokeLinecap="round" opacity="0.7" />
      <line x1="48" y1="325" x2="62" y2="338" stroke="#7A5C10" strokeWidth="8" strokeLinecap="round" />

      {/* 오른팔 — 엄지 척 */}
      <path d="M186 230 Q210 252 214 272" stroke="#222" strokeWidth="22" strokeLinecap="round" fill="none" />
      <circle cx="212" cy="275" r="14" fill="url(#duo-skin)" />
      <path d="M206 268 Q204 258 210 255 Q218 254 218 262 Q218 268 214 272" fill="url(#duo-skin)" stroke="#E8C090" strokeWidth="1" />

      {/* 머리 */}
      <circle cx="138" cy="158" r="70" fill="url(#duo-skin)" />
      <path d="M95 140 Q110 108 138 102 Q166 108 181 140" fill="#1A1A1A" />
      <ellipse cx="80" cy="172" rx="13" ry="22" fill="#1A1A1A" />
      <ellipse cx="196" cy="172" rx="13" ry="22" fill="#1A1A1A" />

      {/* 셜록 사슴가죽 모자 */}
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
      <path
        d="M115 102 Q124 92 130 97 Q136 92 145 102
           Q138 107 130 103 Q122 107 115 102 Z"
        fill="#111"
      />
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


      {/* ══════════════════════════════════════════
          여자 탐정 (오른쪽) — 베이지 트렌치코트
          ══════════════════════════════════════════ */}

      <ellipse cx="302" cy="355" rx="60" ry="9" fill="#D97706" opacity="0.18" />

      {/* 긴 머리카락 뒤 */}
      <path d="M248 222 Q240 290 244 348" stroke="#1A1A1A" strokeWidth="36" strokeLinecap="round" fill="none" />
      <path d="M356 222 Q364 290 360 348" stroke="#1A1A1A" strokeWidth="30" strokeLinecap="round" fill="none" />

      {/* 코트 본체 */}
      <path
        d="M248 228 Q253 315 255 348 L349 348 Q351 315 356 228
           Q340 244 302 246 Q264 244 248 228 Z"
        fill="url(#duo-coat)"
      />
      {/* 코트 칼라/라펠 */}
      <path
        d="M252 218 Q265 232 302 228 Q339 232 352 218
           Q344 208 332 213 Q320 218 302 220 Q284 218 272 213 Q260 208 252 218 Z"
        fill="#C0B090"
      />
      <line x1="302" y1="220" x2="302" y2="330" stroke="#A09070" strokeWidth="2" />

      {/* 빨간 단추 4개 */}
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
      <circle cx="214" cy="287" r="13" fill="url(#duo-skin)" />
      <rect x="202" y="284" width="14" height="26" rx="5" fill="#888" />
      <ellipse cx="209" cy="284" rx="9" ry="6" fill="#AAA" />
      <ellipse cx="209" cy="283" rx="6" ry="4" fill="#FFE566" opacity="0.85" />
      <path d="M200 278 Q209 270 218 278" stroke="#FFE566" strokeWidth="1.5" fill="none" opacity="0.6" />

      {/* 오른팔 — V 사인 */}
      <path d="M352 236 Q374 256 378 272" stroke="#B8A880" strokeWidth="22" strokeLinecap="round" fill="none" />
      <circle cx="377" cy="276" r="13" fill="url(#duo-skin)" />
      <path d="M373 272 Q371 258 376 250" stroke="url(#duo-skin)" strokeWidth="9" strokeLinecap="round" fill="none" />
      <path d="M376 250 Q378 244 381 248" stroke="#F5C8A0" strokeWidth="3" strokeLinecap="round" fill="none" />
      <path d="M381 273 Q381 259 384 251" stroke="url(#duo-skin)" strokeWidth="9" strokeLinecap="round" fill="none" />
      <path d="M384 251 Q386 245 389 249" stroke="#F5C8A0" strokeWidth="3" strokeLinecap="round" fill="none" />

      {/* 머리 */}
      <circle cx="302" cy="155" r="72" fill="url(#duo-skin)" />
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

      {/* 눈 왼쪽 (속눈썹) */}
      <ellipse cx="280" cy="156" rx="15" ry="16" fill="white" />
      <circle cx="280" cy="158" r="10" fill="#201810" />
      <circle cx="284" cy="154" r="4.2" fill="white" />
      <circle cx="277" cy="162" r="1.8" fill="white" opacity="0.55" />
      {[[267, 145, 270, 140], [273, 143, 274, 137], [280, 141, 281, 136], [287, 143, 289, 137], [293, 145, 297, 141]].map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#111" strokeWidth="2.2" strokeLinecap="round" />
      ))}

      {/* 눈 오른쪽 (속눈썹) */}
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

      {/* 장식 */}
      <text x="390" y="80" fontSize="20" opacity="0.65">✨</text>
      <text x="15" y="90" fontSize="15" opacity="0.55">⭐</text>
      <text x="200" y="38" fontSize="13" opacity="0.45">✦</text>
      <text x="380" y="200" fontSize="12" opacity="0.4">✦</text>
    </svg>
  );
}
