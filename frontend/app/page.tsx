import Link from "next/link";
import { Bell, Clock, MapPin, ChevronRight } from "lucide-react";
import DetectiveDuo from "@/components/DetectiveDuo";
import DetectiveGirl from "@/components/DetectiveGirl";
import SearchBar from "@/components/SearchBar";

const HOW_IT_WORKS = [
  {
    step: "01",
    icon: "🗓️",
    title: "날짜와 지역 선택",
    desc: "원하는 날짜와 지역을 고르면 예약 가능한 카페와 테마가 한눈에 표시됩니다.",
  },
  {
    step: "02",
    icon: "🔍",
    title: "빈자리 실시간 확인",
    desc: "15분마다 자동 갱신되는 예약 현황을 한 화면에서 확인하세요.",
  },
  {
    step: "03",
    icon: "🔔",
    title: "빈자리 알림 받기",
    desc: "마감된 테마도 걱정 없어요. 빈자리가 나면 이메일이나 카카오로 즉시 알려드립니다.",
  },
];

// ── 오늘 강남 빈자리 (서버 컴포넌트 — 실제 API) ──────────────
type CafePreview = {
  id: string;
  name: string;
  branch_name: string | null;
  address: string;
  themes: { slots: { status: string }[] }[];
};

async function TodayCafesSection() {
  const today = new Date().toISOString().split("T")[0];
  let cafes: CafePreview[] = [];

  try {
    const res = await fetch(
      `http://localhost:8000/api/v1/search?date=${today}&area=gangnam`,
      { next: { revalidate: 900 } } // 15분 캐시
    );
    if (res.ok) {
      const data = await res.json();
      cafes = (data.cafes ?? []).slice(0, 3);
    }
  } catch {
    // 백엔드 미기동 시 fallback — 섹션 숨김
  }

  if (cafes.length === 0) return null;

  return (
    <section className="py-20 bg-stone-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-end justify-between mb-8">
          <div>
            <h2 className="text-3xl font-extrabold text-stone-900 mb-1">
              오늘 강남 빈자리
            </h2>
            <p className="text-stone-500 text-sm flex items-center gap-1">
              <Clock size={14} />
              방금 전 갱신됨
            </p>
          </div>
          <Link
            href={`/search?date=${today}&area=gangnam`}
            className="text-brand-600 font-semibold text-sm hover:underline flex items-center gap-1"
          >
            전체 보기 <ChevronRight size={16} />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cafes.map((cafe) => {
            const allSlots = cafe.themes.flatMap((t) => t.slots);
            const availableCount = allSlots.filter(
              (s) => s.status === "available"
            ).length;
            const themeCount = cafe.themes.length;

            return (
              <Link
                key={cafe.id}
                href={`/search?date=${today}&area=gangnam`}
                className="card p-5 hover:border-brand-200 transition-all group"
              >
                {/* 카페 헤더 */}
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-bold text-stone-900 group-hover:text-brand-700 transition-colors">
                      {cafe.name}
                    </h3>
                    <p className="text-stone-500 text-sm flex items-center gap-1">
                      <MapPin size={12} />
                      {cafe.branch_name ?? cafe.address.split(" ").slice(0, 3).join(" ")}
                    </p>
                  </div>
                  <span className="text-xl">🔐</span>
                </div>

                {/* 가용 현황 */}
                <div className="flex items-center justify-between pt-3 border-t border-stone-100">
                  <span className="text-sm text-stone-500">
                    총 {themeCount}개 테마
                  </span>
                  <span
                    className={`font-semibold text-sm ${
                      availableCount > 0 ? "text-emerald-600" : "text-rose-500"
                    }`}
                  >
                    {availableCount > 0
                      ? `🟢 ${availableCount}개 예약 가능`
                      : "🔴 전체 마감"}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default async function HomePage() {
  return (
    <div>
      {/* ── 히어로 섹션 ──────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-brand-50 via-amber-50 to-yellow-100 min-h-[88vh] flex items-center">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 w-full">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">

            {/* 왼쪽: 텍스트 + 검색 */}
            <div className="order-2 lg:order-1">
              {/* 배지 */}
              <div className="inline-flex items-center gap-2 bg-brand-200 text-brand-700
                               rounded-full px-4 py-1.5 text-sm font-semibold mb-6">
                <span className="w-2 h-2 bg-brand-500 rounded-full animate-pulse" />
                전국 316개 카페 · MVP 베타
              </div>

              {/* 헤드라인 */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-stone-900
                              leading-tight mb-5">
                방탈출 빈자리를<br />
                <span className="text-brand-500 relative">
                  한눈에
                  {/* 밑줄 장식 */}
                  <svg className="absolute -bottom-2 left-0 w-full" viewBox="0 0 200 8" fill="none">
                    <path d="M0 6 Q50 0 100 4 Q150 8 200 4" stroke="#FBBF24" strokeWidth="4" strokeLinecap="round"/>
                  </svg>
                </span>
              </h1>

              <p className="text-stone-600 text-lg leading-relaxed mb-8 max-w-md">
                여러 방탈출 카페 사이트를 일일이 돌아다닐 필요 없어요.
                <br />
                <strong>이스케이프맵</strong>에서 원하는 날짜·지역의
                예약 현황을 바로 확인하고, 빈자리 알림도 받아보세요.
              </p>

              {/* 검색 바 */}
              <SearchBar className="max-w-xl" />

              {/* 통계 */}
              <div className="flex items-center gap-6 mt-8">
                {[
                  { value: "316+", label: "전국 카페" },
                  { value: "32+",  label: "크롤링 테마" },
                  { value: "15분", label: "갱신 주기" },
                ].map((stat) => (
                  <div key={stat.label} className="text-center">
                    <p className="text-2xl font-extrabold text-stone-900">{stat.value}</p>
                    <p className="text-xs text-stone-500 font-medium">{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* 오른쪽: 탐정 듀오 */}
            <div className="order-1 lg:order-2 flex justify-center">
              <div className="relative w-full max-w-lg animate-float">
                <DetectiveDuo />

                {/* 말풍선 — 남자 탐정 위쪽 */}
                <div className="absolute top-4 left-2 sm:left-6 bg-white rounded-2xl rounded-tl-none
                                 shadow-lg px-4 py-2.5 text-sm font-semibold text-stone-800
                                 border border-brand-200">
                  🔍 빈자리 발견!
                  <div className="absolute top-0 left-0 w-0 h-0
                                   border-r-8 border-r-transparent
                                   border-b-8 border-b-white
                                   -translate-y-full" />
                </div>

                {/* 알림 카드 — 하단 */}
                <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-white rounded-2xl shadow-lg
                                 p-3 border border-brand-100 flex items-center gap-2.5 text-sm whitespace-nowrap">
                  <div className="w-8 h-8 bg-brand-100 rounded-full flex items-center justify-center text-base shrink-0">
                    🔔
                  </div>
                  <div>
                    <p className="font-semibold text-stone-800 text-xs">빈자리 알림</p>
                    <p className="text-stone-500 text-xs">비트포비아 던전 13:00</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 이용 방법 (3단계) ────────────────────────────────── */}
      <section className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-extrabold text-stone-900 mb-3">
              이렇게 사용하세요
            </h2>
            <p className="text-stone-500">3단계면 충분해요</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {HOW_IT_WORKS.map((item, i) => (
              <div
                key={item.step}
                className="relative p-6 rounded-2xl border-2 border-brand-100
                           hover:border-brand-300 hover:bg-brand-50 transition-all duration-200 group"
              >
                {/* 단계 번호 */}
                <span className="absolute -top-3 -left-3 bg-brand-400 text-stone-900
                                  text-xs font-black w-7 h-7 rounded-full flex items-center justify-center
                                  shadow-sm">
                  {item.step}
                </span>

                {/* 화살표 (마지막 제외) */}
                {i < HOW_IT_WORKS.length - 1 && (
                  <ChevronRight
                    size={20}
                    className="absolute -right-4 top-1/2 -translate-y-1/2 text-brand-300
                               hidden md:block z-10"
                  />
                )}

                <div className="text-4xl mb-4">{item.icon}</div>
                <h3 className="text-lg font-bold text-stone-900 mb-2">{item.title}</h3>
                <p className="text-stone-500 text-sm leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 오늘의 강남 빈자리 (실제 API) ────────────────────── */}
      <TodayCafesSection />

      {/* ── 알림 CTA 배너 ────────────────────────────────────── */}
      <section className="py-16 bg-gradient-to-r from-brand-400 to-amber-400 overflow-hidden">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex items-center gap-6 lg:gap-12">
            {/* 여자 탐정 — 손전등으로 텍스트 쪽을 비추는 느낌 */}
            <div className="shrink-0 hidden lg:block">
              <DetectiveGirl className="w-44" />
            </div>

            {/* 텍스트 + 버튼 */}
            <div className="flex-1 text-center lg:text-left">
              <div className="text-4xl mb-3">🔔</div>
              <h2 className="text-3xl font-extrabold text-stone-900 mb-3">
                원하는 테마가 마감됐나요?
              </h2>
              <p className="text-stone-800 text-lg mb-8">
                빈자리 알림을 등록하면 자리가 나는 순간 바로 알려드립니다.
                <br />
                이메일 또는 카카오톡으로 즉시 수신.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center lg:justify-start">
                <Link
                  href="/register"
                  className="bg-stone-900 text-white font-bold px-8 py-4 rounded-xl
                             hover:bg-stone-800 transition-colors shadow-md text-center"
                >
                  <Bell size={18} className="inline mr-2" />
                  빈자리 알림 무료 등록
                </Link>
                <Link
                  href="/search"
                  className="bg-white/80 text-stone-900 font-bold px-8 py-4 rounded-xl
                             hover:bg-white transition-colors text-center"
                >
                  먼저 둘러보기
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
