"use client";

import { useState } from "react";
import clsx from "clsx";

type TimeSlot = {
  time: string;           // "14:00"
  status: "available" | "full" | "closed";
  availableSlots?: number;
  bookingUrl?: string;
};

type TimeSlotGridProps = {
  themeId: number;
  themeName: string;
  slots: TimeSlot[];
  onAlertClick: (themeId: number, themeName: string, time: string) => void;
};

const STATUS_LABEL = {
  available: "예약 가능",
  full: "마감",
  closed: "운영 안 함",
};

export default function TimeSlotGrid({
  themeId,
  themeName,
  slots,
  onAlertClick,
}: TimeSlotGridProps) {
  const [hoveredTime, setHoveredTime] = useState<string | null>(null);

  function handleSlotClick(slot: TimeSlot) {
    if (slot.status === "available" && slot.bookingUrl) {
      // 제휴 추적 링크로 이동
      window.open(`${slot.bookingUrl}?ref=escapemap`, "_blank");
    } else if (slot.status === "full") {
      // 마감된 시간대 → 알림 등록
      onAlertClick(themeId, themeName, slot.time);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {slots.map((slot) => (
        <div key={slot.time} className="relative">
          <button
            onClick={() => handleSlotClick(slot)}
            onMouseEnter={() => setHoveredTime(slot.time)}
            onMouseLeave={() => setHoveredTime(null)}
            className={clsx(
              "border rounded-xl px-3 py-2 text-sm font-semibold transition-all duration-150",
              slot.status === "available" && "timeslot-available",
              slot.status === "full" && "timeslot-full",
              slot.status === "closed" && "timeslot-closed"
            )}
          >
            <div className="text-center">
              <div>{slot.time}</div>
              {slot.status === "available" && slot.availableSlots !== undefined && (
                <div className="text-xs font-normal opacity-80">
                  {slot.availableSlots}자리
                </div>
              )}
              {slot.status === "full" && (
                <div className="text-xs font-normal opacity-70">🔔 알림</div>
              )}
            </div>
          </button>

          {/* 툴팁 */}
          {hoveredTime === slot.time && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                             bg-stone-900 text-white text-xs rounded-lg px-3 py-1.5
                             whitespace-nowrap z-10 shadow-lg">
              {slot.status === "available"
                ? "클릭하여 예약 페이지로 이동"
                : slot.status === "full"
                ? "클릭하여 빈자리 알림 등록"
                : "운영하지 않는 시간대"}
              {/* 툴팁 꼬리 */}
              <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0
                               border-l-4 border-r-4 border-t-4
                               border-l-transparent border-r-transparent border-t-stone-900" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
