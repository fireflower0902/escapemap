"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Clock, ChevronDown, ChevronUp, MapPin, Star, Timer, ExternalLink, Calendar, Search } from "lucide-react";
import TimeSlotGrid from "@/components/TimeSlotGrid";
import AlertModal from "@/components/AlertModal";
import DetectiveBoy from "@/components/DetectiveBoy";

const AREAS = [
  { value: "gangnam",    label: "강남/역삼" },
  { value: "hongdae",   label: "홍대/합정" },
  { value: "sinchon",   label: "신촌/이대" },
  { value: "jamsil",    label: "잠실/송파" },
  { value: "itaewon",   label: "이태원/한남" },
  { value: "myeongdong",label: "명동/종로" },
  { value: "daehakro",  label: "대학로" },
  { value: "sinlim",    label: "신림" },
  { value: "busan",     label: "부산" },
  { value: "daegu",     label: "대구" },
  { value: "gwangju",   label: "광주" },
  { value: "daejeon",   label: "대전" },
  { value: "incheon",   label: "인천" },
  { value: "gyeonggi",  label: "경기" },
  { value: "gangwon",   label: "강원" },
];

// 07:00 ~ 23:00, 30분 단위
const TIME_OPTIONS = Array.from({ length: 33 }, (_, i) => {
  const totalMin = 7 * 60 + i * 30;
  const h = String(Math.floor(totalMin / 60)).padStart(2, "0");
  const m = String(totalMin % 60).padStart(2, "0");
  return `${h}:${m}`;
});

// ── API 응답 타입 ──────────────────────────────────────────────
type ApiSlot = {
  time: string;
  status: "available" | "full" | "closed";
  booking_url: string | null;
};

type ApiTheme = {
  id: number;
  name: string;
  difficulty: number;
  duration_min: number | null;
  poster_url: string | null;
  slots: ApiSlot[];
};

type ApiCafe = {
  id: string;
  name: string;
  branch_name: string | null;
  address: string;
  website_url: string | null;
  crawled: boolean;
  themes: ApiTheme[];
};

// ── 지역 코드 → 표시 이름 ────────────────────────────────────
const AREA_LABELS: Record<string, string> = {
  gangnam:    "강남/역삼",
  hongdae:    "홍대/합정",
  sinchon:    "신촌/이대",
  jamsil:     "잠실/송파",
  itaewon:    "이태원/한남",
  myeongdong: "명동/종로",
  daehakro:   "대학로",
  sinlim:     "신림",
  busan:      "부산",
  daegu:      "대구",
  gwangju:    "광주",
  daejeon:    "대전",
  incheon:    "인천",
  gyeonggi:   "경기",
  gangwon:    "강원",
};

const DIFFICULTY_STARS = (d: number) =>
  Array.from({ length: 5 }, (_, i) => (
    <Star
      key={i}
      size={12}
      className={i < d ? "text-brand-500 fill-brand-500" : "text-stone-300 fill-stone-300"}
    />
  ));

// ── 포스터 썸네일 컴포넌트 ────────────────────────────────────
function ThemePoster({ url, name }: { url: string | null; name: string }) {
  const [imgError, setImgError] = useState(false);

  if (!url || imgError) {
    return (
      <div className="w-16 h-20 bg-gradient-to-b from-stone-800 to-stone-900
                       rounded-xl flex items-center justify-center text-3xl shrink-0 shadow-sm">
        🔐
      </div>
    );
  }

  return (
    <div className="w-16 h-20 rounded-xl overflow-hidden shrink-0 shadow-sm bg-stone-800">
      <img
        src={url}
        alt={name}
        className="w-full h-full object-cover"
        onError={() => setImgError(true)}
      />
    </div>
  );
}

// ── 검색 결과 본체 ────────────────────────────────────────────
function SearchResults() {
  const router = useRouter();
  const params = useSearchParams();
  const date = params.get("date") || new Date().toISOString().split("T")[0];
  const area = params.get("area") || "gangnam";

  // 폼 로컬 state (URL 파라미터 변경 전 편집 중인 값)
  const [formDate, setFormDate] = useState(date);
  const [formArea, setFormArea] = useState(area);
  const today = new Date().toISOString().split("T")[0];
  const dateInputRef = useRef<HTMLInputElement>(null);

  // URL 파라미터가 바뀌면 폼도 동기화
  useEffect(() => { setFormDate(date); }, [date]);
  useEffect(() => { setFormArea(area); }, [area]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    router.push(`/search?date=${formDate}&area=${formArea}`);
  }

  const [cafes, setCafes] = useState<ApiCafe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCafe, setExpandedCafe] = useState<string | null>(null);
  const [alertModal, setAlertModal] = useState<{
    open: boolean;
    themeId: number;
    themeName: string;
    time: string;
  }>({ open: false, themeId: 0, themeName: "", time: "" });
  const [timeFrom, setTimeFrom] = useState("");
  const [timeTo, setTimeTo] = useState("");
  const [timePickerOpen, setTimePickerOpen] = useState(false);
  const [timePickerStep, setTimePickerStep] = useState<"from" | "to">("from");
  const timePickerRef = useRef<HTMLDivElement>(null);

  // 시간 드롭다운 외부 클릭 시 닫기
  useEffect(() => {
    if (!timePickerOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (timePickerRef.current && !timePickerRef.current.contains(e.target as Node)) {
        setTimePickerOpen(false);
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [timePickerOpen]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setCafes([]);

    fetch(`/api/v1/search?date=${date}&area=${area}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setCafes(data.cafes ?? []);
        // 첫 번째 카페 자동 펼침
        if (data.cafes?.length > 0) {
          setExpandedCafe(data.cafes[0].id);
        }
      })
      .catch((err) => {
        console.error(err);
        setError("데이터를 불러오지 못했습니다. 백엔드 서버가 실행 중인지 확인하세요.");
      })
      .finally(() => setLoading(false));
  }, [date, area]);

  const dateFormatted = new Date(date).toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "short",
  });

  // 슬롯 시작시간이 선택한 시간 범위 안에 있는지 확인
  function isSlotInRange(timeStr: string) {
    if (!timeFrom && !timeTo) return true;
    const [h, m] = timeStr.split(":").map(Number);
    const slotMin = h * 60 + m;
    if (timeFrom) {
      const [fh, fm] = timeFrom.split(":").map(Number);
      if (slotMin < fh * 60 + fm) return false;
    }
    if (timeTo) {
      const [th, tm] = timeTo.split(":").map(Number);
      if (slotMin > th * 60 + tm) return false;
    }
    return true;
  }

  function openAlert(themeId: number, themeName: string, time: string) {
    setAlertModal({ open: true, themeId, themeName, time });
  }

  return (
    <div className="min-h-screen bg-stone-50">
      {/* 통합 검색 바 */}
      <div className="bg-white border-b border-stone-100 py-4 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <form
            onSubmit={handleSearch}
            className="bg-white rounded-2xl shadow-lg border border-stone-100 p-2
                       flex flex-col sm:flex-row items-stretch gap-2"
          >
            {/* 날짜 */}
            <div
              className="flex items-center gap-3 px-4 py-3 rounded-xl
                         bg-stone-50 hover:bg-brand-50 transition-colors cursor-pointer sm:flex-1"
              onClick={() => { try { dateInputRef.current?.showPicker(); } catch {} }}
            >
              <Calendar size={20} className="text-brand-500 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-stone-400 font-medium leading-none mb-1">날짜</p>
                <input
                  ref={dateInputRef}
                  type="date"
                  value={formDate}
                  min={today}
                  onChange={(e) => setFormDate(e.target.value)}
                  className="bg-transparent text-stone-800 font-semibold text-lg w-full outline-none cursor-pointer"
                />
              </div>
            </div>

            <div className="hidden sm:block w-px bg-stone-200 my-2" />

            {/* 지역 */}
            <label className="flex items-center gap-3 px-4 py-3 rounded-xl
                               bg-stone-50 hover:bg-brand-50 transition-colors cursor-pointer sm:flex-1">
              <MapPin size={20} className="text-brand-500 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-stone-400 font-medium leading-none mb-1">지역</p>
                <select
                  value={formArea}
                  onChange={(e) => setFormArea(e.target.value)}
                  className="bg-transparent text-stone-800 font-semibold text-lg w-full outline-none cursor-pointer appearance-none"
                >
                  {AREAS.map((a) => (
                    <option key={a.value} value={a.value}>{a.label}</option>
                  ))}
                </select>
              </div>
            </label>

            <div className="hidden sm:block w-px bg-stone-200 my-2" />

            {/* 시작 시간 ~ 종료 시간 (커스텀 피커) */}
            <div
              ref={timePickerRef}
              className="relative flex items-center gap-3 px-4 py-3 rounded-xl
                         bg-stone-50 hover:bg-brand-50 transition-colors cursor-pointer sm:flex-1"
              onClick={() => {
                if (timePickerOpen) {
                  setTimePickerOpen(false);
                } else {
                  setTimePickerStep("from");
                  setTimePickerOpen(true);
                }
              }}
            >
              <Clock size={20} className="text-brand-500 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-stone-400 font-medium leading-none mb-1">시작 시간</p>
                <div className="flex items-center gap-2">
                  <span className={`font-semibold text-lg ${
                    timePickerOpen && timePickerStep === "from"
                      ? "text-brand-500"
                      : timeFrom ? "text-stone-800" : "text-stone-400"
                  }`}>
                    {timeFrom || "전체"}
                  </span>
                  <span className="text-stone-400 text-lg font-medium shrink-0">~</span>
                  <span className={`font-semibold text-lg ${
                    timePickerOpen && timePickerStep === "to"
                      ? "text-brand-500"
                      : timeTo ? "text-stone-800" : "text-stone-400"
                  }`}>
                    {timeTo || "전체"}
                  </span>
                  {(timeFrom || timeTo) && !timePickerOpen && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setTimeFrom(""); setTimeTo(""); }}
                      className="text-xs text-stone-400 hover:text-stone-600 underline transition-colors shrink-0"
                    >
                      초기화
                    </button>
                  )}
                </div>
              </div>

              {/* 커스텀 시간 드롭다운 */}
              {timePickerOpen && (
                <div
                  className="absolute top-full left-0 mt-2 z-50 bg-white rounded-2xl
                             shadow-xl border border-stone-100 p-4 w-72"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* 단계 헤더 */}
                  <div className="flex items-center justify-between mb-3">
                    {timePickerStep === "to" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => setTimePickerStep("from")}
                          className="text-sm text-stone-400 hover:text-stone-600 transition-colors"
                        >
                          ← Time From
                        </button>
                        <p className="text-sm font-semibold text-stone-700">Time To</p>
                      </>
                    ) : (
                      <p className="text-sm font-semibold text-stone-700">Time From</p>
                    )}
                  </div>

                  {/* 전체(제한 없음) 옵션 */}
                  <button
                    type="button"
                    onClick={() => {
                      if (timePickerStep === "from") {
                        setTimeFrom("");
                        setTimeTo("");
                      } else {
                        setTimeTo("");
                      }
                      setTimePickerOpen(false);
                    }}
                    className="w-full text-sm py-2 rounded-xl text-stone-400 hover:bg-stone-50
                               hover:text-stone-600 transition-colors mb-2 border border-dashed border-stone-200"
                  >
                    전체 (제한 없음)
                  </button>

                  {/* 시간 그리드 */}
                  <div className="grid grid-cols-4 gap-1 max-h-56 overflow-y-auto">
                    {(timePickerStep === "from"
                      ? TIME_OPTIONS
                      : TIME_OPTIONS.filter((t) => !timeFrom || t >= timeFrom)
                    ).map((t) => {
                      const isSelected =
                        timePickerStep === "from" ? t === timeFrom : t === timeTo;
                      return (
                        <button
                          key={t}
                          type="button"
                          onClick={() => {
                            if (timePickerStep === "from") {
                              setTimeFrom(t);
                              setTimeTo("");
                              setTimePickerStep("to");
                            } else {
                              setTimeTo(t);
                              setTimePickerOpen(false);
                            }
                          }}
                          className={`text-sm py-2 rounded-lg font-medium transition-colors text-center
                            ${isSelected
                              ? "bg-brand-400 text-stone-900"
                              : "hover:bg-brand-50 text-stone-700"}`}
                        >
                          {t}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* 검색 버튼 */}
            <button
              type="submit"
              className="flex items-center justify-center gap-2 bg-brand-400 hover:bg-brand-500
                         text-stone-900 font-bold px-6 py-3 rounded-xl transition-all duration-200
                         shadow-sm hover:shadow-md active:scale-95 whitespace-nowrap shrink-0 text-lg"
            >
              <Search size={18} />
              <span>빈자리 찾기</span>
            </button>
          </form>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* 검색 결과 헤더 */}
        <div className="flex items-end justify-between mb-6 gap-4">
          <div className="flex items-end gap-4">
            <DetectiveBoy className="w-20 shrink-0 hidden sm:block" />
            <div>
              <h1 className="text-2xl font-extrabold text-stone-900">
                {AREA_LABELS[area] ?? area} · {dateFormatted}
              </h1>
              <p className="text-stone-500 text-sm flex items-center gap-1 mt-1">
                <Clock size={14} />
                {loading
                  ? "불러오는 중..."
                  : `방금 전 갱신 · ${cafes.filter((c) => c.crawled).length}개 카페 수집 완료`}
              </p>
            </div>
          </div>

          {/* 범례 */}
          <div className="hidden md:flex items-center gap-3 text-xs text-stone-600 shrink-0">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-emerald-200 border border-emerald-400 rounded" />
              예약 가능
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-rose-100 border border-rose-300 rounded" />
              마감 (알림 등록 가능)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-stone-100 border border-stone-200 rounded" />
              운영 안 함
            </span>
          </div>
        </div>

        {/* 로딩 */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-stone-400">
            <div className="text-5xl animate-bounce">🔍</div>
            <p className="font-medium">빈자리 찾는 중...</p>
          </div>
        )}

        {/* 에러 */}
        {!loading && error && (
          <div className="card p-8 text-center text-stone-500">
            <div className="text-4xl mb-3">⚠️</div>
            <p>{error}</p>
          </div>
        )}

        {/* 결과 없음 */}
        {!loading && !error && cafes.length === 0 && (
          <div className="card p-8 text-center text-stone-500">
            <div className="text-4xl mb-3">🔐</div>
            <p className="font-semibold mb-1">예약 정보가 없습니다</p>
            <p className="text-sm">
              해당 날짜·지역의 데이터가 아직 수집되지 않았습니다.
            </p>
          </div>
        )}

        {/* 카페 목록 */}
        {!loading && !error && cafes.length > 0 && (
          <div className="space-y-4">
            {/* ── 크롤링 완료 카페 ── */}
            {cafes.filter((c) => c.crawled).map((cafe) => {
              const isExpanded = expandedCafe === cafe.id;

              // 시간 범위 내 슬롯만 집계
              const totalAvailable = cafe.themes
                .flatMap((t) => t.slots)
                .filter((s) => s.status === "available" && isSlotInRange(s.time)).length;

              // 시간 범위 내 슬롯이 있는 테마만
              const visibleThemes = cafe.themes.filter((t) =>
                t.slots.some((s) => isSlotInRange(s.time))
              );

              // 시간 범위에 해당하는 슬롯이 하나도 없으면 카드 숨김
              if (visibleThemes.length === 0) return null;

              return (
                <div key={cafe.id} className="card overflow-hidden">
                  {/* 카페 헤더 (접기/펼치기) */}
                  <button
                    onClick={() =>
                      setExpandedCafe(isExpanded ? null : cafe.id)
                    }
                    className="w-full p-5 flex items-center justify-between text-left hover:bg-stone-50 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-brand-100 rounded-xl flex items-center justify-center text-2xl shrink-0">
                        🔐
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h2 className="font-extrabold text-stone-900 text-lg">
                            {cafe.name}{cafe.branch_name ? ` ${cafe.branch_name}` : ""}
                          </h2>
                        </div>
                        <p className="text-stone-500 text-sm flex items-center gap-1 mt-0.5">
                          <MapPin size={12} />
                          {cafe.address}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      <span
                        className={`font-bold text-sm ${
                          totalAvailable > 0
                            ? "text-emerald-600"
                            : "text-rose-500"
                        }`}
                      >
                        {totalAvailable > 0
                          ? `🟢 ${totalAvailable}개 가능`
                          : "🔴 전체 마감"}
                      </span>
                      {isExpanded ? (
                        <ChevronUp size={20} className="text-stone-400" />
                      ) : (
                        <ChevronDown size={20} className="text-stone-400" />
                      )}
                    </div>
                  </button>

                  {/* 테마 목록 (펼쳐졌을 때) */}
                  {isExpanded && (
                    <div className="border-t border-stone-100 divide-y divide-stone-50">
                      {visibleThemes.map((theme) => {
                        // 시간 범위 내 슬롯만 표시
                        const mappedSlots = theme.slots
                          .filter((s) => isSlotInRange(s.time))
                          .map((s) => ({
                            time: s.time,
                            status: s.status,
                            bookingUrl: s.booking_url ?? undefined,
                          }));
                        const availableCount = mappedSlots.filter(
                          (s) => s.status === "available"
                        ).length;

                        return (
                          <div key={theme.id} className="p-5">
                            <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                              {/* 테마 포스터 */}
                              <ThemePoster
                                url={theme.poster_url}
                                name={theme.name}
                              />

                              {/* 테마 정보 + 타임슬롯 */}
                              <div className="flex-1 min-w-0">
                                <div className="flex flex-wrap items-center gap-2 mb-1">
                                  <h3 className="font-bold text-stone-900">
                                    {theme.name}
                                  </h3>
                                  <span
                                    className={
                                      availableCount > 0
                                        ? "badge-available"
                                        : "badge-full"
                                    }
                                  >
                                    {availableCount > 0
                                      ? `${availableCount}개 가능`
                                      : "전체 마감"}
                                  </span>
                                </div>

                                {/* 메타 정보 */}
                                <div className="flex flex-wrap items-center gap-3 text-xs text-stone-500 mb-3">
                                  <span className="flex items-center gap-1">
                                    난이도 {DIFFICULTY_STARS(theme.difficulty)}
                                  </span>
                                  {theme.duration_min && (
                                    <span className="flex items-center gap-1">
                                      <Timer size={12} />
                                      {theme.duration_min}분
                                    </span>
                                  )}
                                </div>

                                {/* 타임슬롯 그리드 */}
                                {mappedSlots.length > 0 ? (
                                  <TimeSlotGrid
                                    themeId={theme.id}
                                    themeName={theme.name}
                                    slots={mappedSlots}
                                    onAlertClick={openAlert}
                                  />
                                ) : (
                                  <p className="text-sm text-stone-400">
                                    이 날짜의 스케줄 정보가 없습니다.
                                  </p>
                                )}

                                <p className="text-xs text-stone-400 mt-2">
                                  🟢 클릭 시 예약 페이지로 이동 · 🔴 클릭 시
                                  빈자리 알림 등록
                                </p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}

            {/* ── 구현 예정 카페 구분선 + 목록 ── */}
            {cafes.some((c) => !c.crawled) && (
              <>
                <div className="flex items-center gap-3 pt-2">
                  <div className="flex-1 h-px bg-stone-200" />
                  <span className="text-sm text-stone-400 font-medium shrink-0">
                    구현 예정 ({cafes.filter((c) => !c.crawled).length}개)
                  </span>
                  <div className="flex-1 h-px bg-stone-200" />
                </div>

                {cafes.filter((c) => !c.crawled).map((cafe) => (
                  <div key={cafe.id} className="card overflow-hidden opacity-60">
                    <div className="p-5 flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-stone-100 rounded-xl flex items-center justify-center text-2xl shrink-0">
                          🔐
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <h2 className="font-extrabold text-stone-700 text-lg">
                              {cafe.name}{cafe.branch_name ? ` ${cafe.branch_name}` : ""}
                            </h2>
                            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                              구현 예정
                            </span>
                          </div>
                          <p className="text-stone-400 text-sm flex items-center gap-1 mt-0.5">
                            <MapPin size={12} />
                            {cafe.address}
                          </p>
                        </div>
                      </div>
                      {cafe.website_url && (
                        <a
                          href={cafe.website_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-brand-600 transition-colors shrink-0 ml-4"
                        >
                          <ExternalLink size={14} />
                          <span className="hidden sm:inline">예약 사이트</span>
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* 알림 모달 */}
      <AlertModal
        isOpen={alertModal.open}
        onClose={() => setAlertModal((prev) => ({ ...prev, open: false }))}
        themeId={alertModal.themeId}
        themeName={alertModal.themeName}
        date={date}
        timeSlot={alertModal.time}
      />
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="text-5xl mb-4 animate-bounce">🔍</div>
            <p className="text-stone-500">빈자리 찾는 중...</p>
          </div>
        </div>
      }
    >
      <SearchResults />
    </Suspense>
  );
}
