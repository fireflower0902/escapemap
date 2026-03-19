"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, MapPin, Calendar } from "lucide-react";

const AREAS = [
  { value: "gangnam",    label: "강남/역삼" },
  { value: "hongdae",    label: "홍대/합정" },
  { value: "sinchon",    label: "신촌/이대" },
  { value: "konkuk",     label: "건대/광진" },
  { value: "jamsil",     label: "잠실/송파" },
  { value: "itaewon",    label: "이태원/한남" },
  { value: "myeongdong", label: "명동/종로" },
  { value: "daehakro",   label: "대학로" },
  { value: "sinlim",     label: "신림" },
  { value: "busan",      label: "부산" },
  { value: "daegu",      label: "대구" },
  { value: "gwangju",    label: "광주" },
  { value: "daejeon",    label: "대전" },
  { value: "incheon",    label: "인천" },
  { value: "gyeonggi",   label: "경기" },
  { value: "gangwon",    label: "강원" },
];

export default function SearchBar({ className = "" }: { className?: string }) {
  const router = useRouter();

  // 오늘 날짜를 기본값으로, 최대 +14일까지 선택 가능
  const today = new Date().toISOString().split("T")[0];
  const maxDate = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
  const [date, setDate] = useState(today);
  const [area, setArea] = useState("gangnam");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    router.push(`/search?date=${date}&area=${area}`);
  }

  return (
    <form
      onSubmit={handleSearch}
      className={`bg-white rounded-2xl shadow-lg border border-stone-100 p-2 ${className}`}
    >
      <div className="flex flex-col sm:flex-row gap-2">

        {/* 날짜 선택 */}
        <label className="flex-1 flex items-center gap-2 px-4 py-3 rounded-xl
                           bg-stone-50 hover:bg-brand-50 transition-colors cursor-pointer group">
          <Calendar size={20} className="text-brand-500 shrink-0" />
          <div className="min-w-0">
            <p className="text-sm text-stone-400 font-medium">날짜</p>
            <input
              type="date"
              value={date}
              min={today}
              max={maxDate}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent text-stone-800 font-semibold text-base w-full
                         outline-none cursor-pointer"
            />
          </div>
        </label>

        {/* 구분선 */}
        <div className="hidden sm:block w-px bg-stone-200 my-2" />

        {/* 지역 선택 */}
        <label className="flex-1 flex items-center gap-2 px-4 py-3 rounded-xl
                           bg-stone-50 hover:bg-brand-50 transition-colors cursor-pointer">
          <MapPin size={20} className="text-brand-500 shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-stone-400 font-medium">지역</p>
            <select
              value={area}
              onChange={(e) => setArea(e.target.value)}
              className="bg-transparent text-stone-800 font-semibold text-base w-full
                         outline-none cursor-pointer appearance-none"
            >
              {AREAS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>
        </label>

        {/* 검색 버튼 */}
        <button
          type="submit"
          className="flex items-center justify-center gap-2 bg-brand-400 hover:bg-brand-500
                     text-stone-900 font-bold px-6 py-3 rounded-xl transition-all duration-200
                     shadow-sm hover:shadow-md active:scale-95 whitespace-nowrap"
        >
          <Search size={18} />
          <span>빈자리 찾기</span>
        </button>
      </div>
    </form>
  );
}
