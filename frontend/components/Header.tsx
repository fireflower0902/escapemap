"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

// 자물쇠 + 돋보기 로고 SVG
function LogoIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* 자물쇠 몸체 */}
      <rect x="6" y="14" width="16" height="13" rx="3" fill="#FBBF24" />
      {/* 자물쇠 고리 */}
      <path
        d="M10 14V10C10 7.79 11.79 6 14 6C16.21 6 18 7.79 18 10V14"
        stroke="#D97706"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* 열쇠 구멍 */}
      <circle cx="14" cy="20" r="2" fill="#D97706" />
      <rect x="13" y="20" width="2" height="3" rx="1" fill="#D97706" />
      {/* 돋보기 */}
      <circle cx="23" cy="9" r="4" stroke="#1C1917" strokeWidth="2" />
      <line x1="26" y1="12" x2="29" y2="15" stroke="#1C1917" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-stone-100 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">

          {/* 로고 */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <LogoIcon />
            <span className="text-xl font-bold text-stone-900 group-hover:text-brand-600 transition-colors">
              이스케이프맵
            </span>
          </Link>

          {/* 데스크탑 내비게이션 */}
          <nav className="hidden md:flex items-center gap-1">
            <Link
              href="/search"
              className="px-4 py-2 text-stone-600 hover:text-stone-900 hover:bg-brand-50
                         rounded-lg font-medium transition-all duration-150"
            >
              예약 현황 조회
            </Link>
            <Link
              href="/cafes"
              className="px-4 py-2 text-stone-600 hover:text-stone-900 hover:bg-brand-50
                         rounded-lg font-medium transition-all duration-150"
            >
              카페 목록
            </Link>
            <Link
              href="/alerts"
              className="px-4 py-2 text-stone-600 hover:text-stone-900 hover:bg-brand-50
                         rounded-lg font-medium transition-all duration-150"
            >
              내 알림
            </Link>
          </nav>

          {/* 데스크탑 CTA */}
          <div className="hidden md:flex items-center gap-3">
            <Link href="/login" className="text-stone-600 hover:text-stone-900 font-medium transition-colors">
              로그인
            </Link>
            <Link href="/register" className="btn-primary text-sm py-2">
              무료 가입
            </Link>
          </div>

          {/* 모바일 메뉴 버튼 */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-stone-100 transition-colors"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="메뉴 열기"
          >
            {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {/* 모바일 메뉴 */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-stone-100 py-3 space-y-1">
            {[
              { href: "/search", label: "예약 현황 조회" },
              { href: "/cafes", label: "카페 목록" },
              { href: "/alerts", label: "내 알림" },
              { href: "/login", label: "로그인" },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block px-4 py-2.5 text-stone-700 hover:bg-brand-50
                           rounded-lg font-medium transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <div className="pt-2 px-4">
              <Link href="/register" className="btn-primary block text-center text-sm">
                무료 가입
              </Link>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
