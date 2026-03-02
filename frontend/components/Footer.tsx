import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-stone-900 text-stone-400 mt-auto">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

          {/* 브랜드 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              {/* 미니 자물쇠 아이콘 */}
              <span className="text-brand-400 text-2xl">🔐</span>
              <span className="text-white font-bold text-lg">이스케이프맵</span>
            </div>
            <p className="text-sm leading-relaxed text-stone-500">
              전국 방탈출 카페 예약 현황을<br />
              한눈에 확인하세요.
            </p>
          </div>

          {/* 서비스 */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm uppercase tracking-wider">
              서비스
            </h4>
            <ul className="space-y-2 text-sm">
              {[
                { href: "/search", label: "예약 현황 조회" },
                { href: "/cafes", label: "카페 목록" },
                { href: "/alerts", label: "빈자리 알림" },
              ].map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="hover:text-brand-400 transition-colors"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* 정책 */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm uppercase tracking-wider">
              정책
            </h4>
            <ul className="space-y-2 text-sm">
              {[
                { href: "/privacy", label: "개인정보처리방침" },
                { href: "/terms", label: "이용약관" },
              ].map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="hover:text-brand-400 transition-colors"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-stone-800 mt-8 pt-6 flex flex-col sm:flex-row justify-between items-center gap-2 text-xs text-stone-600">
          <p>© 2026 이스케이프맵. All rights reserved.</p>
          <p>예약은 각 카페 공식 사이트에서 진행됩니다.</p>
        </div>
      </div>
    </footer>
  );
}
