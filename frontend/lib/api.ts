// ── 백엔드 API 호출 함수 모음 ────────────────────────────────
// 모든 API 요청은 이 파일에서 관리합니다.
// next.config.ts에서 /api/* → 백엔드 서버로 프록시 처리됩니다.

import type { Cafe, Theme, Schedule, CreateAlertRequest } from "@/lib/types";

const BASE = "/api/v1";

// ── 공통 fetch 래퍼 ──────────────────────────────────────────
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "알 수 없는 오류" }));
    throw new Error(error.detail ?? `HTTP ${res.status}`);
  }

  return res.json();
}

// ── 카페 ─────────────────────────────────────────────────────

/** 지역 기준 카페 목록 조회 */
export async function getCafes(params: {
  area?: string;
  lat?: number;
  lng?: number;
  radius?: number;
}): Promise<{ cafes: Cafe[]; total: number }> {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)])
  );
  return apiFetch(`/cafes?${query}`);
}

/** 카페 상세 조회 */
export async function getCafe(cafeId: string): Promise<Cafe> {
  return apiFetch(`/cafes/${cafeId}`);
}

/** 카페의 테마 목록 조회 */
export async function getCafeThemes(cafeId: string): Promise<{ themes: Theme[] }> {
  return apiFetch(`/cafes/${cafeId}/themes`);
}

// ── 예약 현황 ─────────────────────────────────────────────────

/** 날짜·지역 기준 예약 현황 조회 */
export async function getSchedules(params: {
  date: string;
  area?: string;
  status?: "available" | "full" | "closed";
}): Promise<{ schedules: Schedule[]; total: number }> {
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)])
  );
  return apiFetch(`/schedules?${query}`);
}

/** 특정 테마의 타임슬롯 조회 */
export async function getThemeSchedules(
  themeId: number,
  date: string
): Promise<{ time_slots: Schedule[] }> {
  return apiFetch(`/themes/${themeId}/schedules?date=${date}`);
}

// ── 알림 ─────────────────────────────────────────────────────

/** 빈자리 알림 등록 */
export async function createAlert(
  data: CreateAlertRequest
): Promise<{ message: string; alert_id: number }> {
  return apiFetch("/alerts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** 알림 취소 */
export async function deleteAlert(alertId: number): Promise<{ message: string }> {
  return apiFetch(`/alerts/${alertId}`, { method: "DELETE" });
}

// ── 인증 ─────────────────────────────────────────────────────

/** 이메일 회원가입 */
export async function register(
  email: string
): Promise<{ message: string; user_id: number }> {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}
