"use client";

import { useState, useRef, useEffect } from "react";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";

const DAYS_AHEAD = 14; // 크롤링 범위와 동일

function toLocalDateStr(d: Date): string {
  return d.toLocaleDateString("en-CA"); // YYYY-MM-DD (로컬 시간 기준)
}

interface DatePickerProps {
  value: string;           // YYYY-MM-DD
  onChange: (date: string) => void;
  label?: string;
  triggerClassName?: string;
  dateClassName?: string;
}

export default function DatePicker({
  value,
  onChange,
  label = "날짜",
  triggerClassName = "",
  dateClassName = "",
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const [toastVisible, setToastVisible] = useState(false);
  const [viewYear, setViewYear] = useState(0);
  const [viewMonth, setViewMonth] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const maxDate = new Date(today.getTime() + DAYS_AHEAD * 24 * 60 * 60 * 1000);
  const todayStr = toLocalDateStr(today);
  const maxStr   = toLocalDateStr(maxDate);

  // 뷰 초기화: value가 바뀔 때마다 해당 월로 이동
  useEffect(() => {
    const d = value ? new Date(value + "T00:00:00") : new Date();
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
  }, [value]);

  // 외부 클릭 시 닫기
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  function showToast() {
    setToastVisible(true);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastVisible(false), 2000);
  }

  function handleDayClick(dateStr: string, disabled: boolean) {
    if (disabled) { showToast(); return; }
    onChange(dateStr);
    setOpen(false);
  }

  function prevMonth() {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(viewYear - 1); }
    else { setViewMonth(viewMonth - 1); }
  }

  function nextMonth() {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(viewYear + 1); }
    else { setViewMonth(viewMonth + 1); }
  }

  const daysInMonth  = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstWeekDay = new Date(viewYear, viewMonth, 1).getDay(); // 0=일

  const displayDate = value
    ? new Date(value + "T00:00:00").toLocaleDateString("ko-KR", {
        year: "numeric", month: "long", day: "numeric", weekday: "short",
      })
    : "날짜 선택";

  return (
    <div ref={wrapperRef} className={`relative ${triggerClassName}`}>
      {/* 트리거 */}
      <div onClick={() => setOpen((o) => !o)} className="flex items-center gap-2 cursor-pointer w-full">
        <Calendar size={20} className="text-brand-500 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-stone-400 font-medium leading-none mb-1">{label}</p>
          <p className={`font-semibold text-stone-800 truncate ${dateClassName}`}>{displayDate}</p>
        </div>
      </div>

      {/* 달력 팝오버 */}
      {open && (
        <div className="absolute top-full left-0 mt-2 z-50 bg-white rounded-2xl shadow-xl border border-stone-100 p-4 w-72">
          {/* 월 이동 헤더 */}
          <div className="flex items-center justify-between mb-3">
            <button type="button" onClick={prevMonth}
              className="p-1.5 hover:bg-stone-100 rounded-lg transition-colors">
              <ChevronLeft size={16} className="text-stone-600" />
            </button>
            <span className="font-bold text-stone-800 text-sm">
              {viewYear}년 {viewMonth + 1}월
            </span>
            <button type="button" onClick={nextMonth}
              className="p-1.5 hover:bg-stone-100 rounded-lg transition-colors">
              <ChevronRight size={16} className="text-stone-600" />
            </button>
          </div>

          {/* 요일 헤더 */}
          <div className="grid grid-cols-7 mb-1">
            {["일","월","화","수","목","금","토"].map((d) => (
              <div key={d} className="text-center text-xs text-stone-400 font-medium py-1">{d}</div>
            ))}
          </div>

          {/* 날짜 그리드 */}
          <div className="grid grid-cols-7 gap-y-0.5">
            {/* 앞쪽 빈칸 */}
            {Array.from({ length: firstWeekDay }).map((_, i) => (
              <div key={`e${i}`} />
            ))}

            {Array.from({ length: daysInMonth }, (_, i) => {
              const day     = i + 1;
              const dateStr = toLocalDateStr(new Date(viewYear, viewMonth, day));
              const disabled = dateStr < todayStr || dateStr > maxStr;
              const isSelected = dateStr === value;
              const isToday    = dateStr === todayStr;

              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => handleDayClick(dateStr, disabled)}
                  className={[
                    "text-sm py-1.5 rounded-lg font-medium transition-colors text-center select-none",
                    isSelected
                      ? "bg-brand-400 text-stone-900"
                      : disabled
                      ? "bg-red-50 text-red-300 cursor-pointer hover:bg-red-100"
                      : isToday
                      ? "bg-emerald-100 ring-2 ring-emerald-400 text-emerald-700 hover:bg-emerald-200"
                      : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100",
                  ].join(" ")}
                >
                  {day}
                </button>
              );
            })}
          </div>

          {/* 하단 버튼 */}
          <div className="flex justify-between mt-3 pt-3 border-t border-stone-100">
            <button
              type="button"
              onClick={() => { onChange(""); setOpen(false); }}
              className="text-xs text-stone-400 hover:text-stone-600 transition-colors"
            >
              삭제
            </button>
            <button
              type="button"
              onClick={() => { onChange(todayStr); setOpen(false); }}
              className="text-xs text-brand-600 font-semibold hover:text-brand-700 transition-colors"
            >
              오늘
            </button>
          </div>

          {/* 조회 불가 토스트 */}
          {toastVisible && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                            bg-stone-800 text-white text-xs font-medium
                            px-3 py-2 rounded-lg whitespace-nowrap shadow-lg
                            animate-fade-in pointer-events-none">
              조회 불가한 날짜입니다.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
