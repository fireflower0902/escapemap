"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, MapPin } from "lucide-react";
import DatePicker from "@/components/DatePicker";
import { AREAS } from "@/lib/areas";

export default function SearchBar({ className = "" }: { className?: string }) {
  const router = useRouter();

  const today = new Date().toLocaleDateString("en-CA");
  const [date, setDate] = useState(today);
  const [area, setArea] = useState("all");

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
        <div className="flex-1 px-4 py-3 rounded-xl bg-stone-50 hover:bg-brand-50 transition-colors">
          <DatePicker
            value={date}
            onChange={(d) => setDate(d || today)}
            label="날짜"
            dateClassName="text-base"
          />
        </div>

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
