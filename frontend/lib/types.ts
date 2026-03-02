// ── 프론트엔드 전체에서 사용하는 타입 정의 ──────────────────
// 백엔드 API의 응답 형태와 동일하게 맞춰야 합니다.

export type Cafe = {
  id: string;
  name: string;
  branch_name: string | null;
  address: string | null;
  phone: string | null;
  website_url: string | null;
  lat: number | null;
  lng: number | null;
};

export type Theme = {
  id: number;
  cafe_id: string;
  name: string;
  description: string | null;
  difficulty: number | null;      // 1~5
  min_players: number | null;
  max_players: number | null;
  duration_min: number | null;
  poster_url: string | null;
  is_active: boolean;
};

export type TimeSlotStatus = "available" | "full" | "closed";

export type Schedule = {
  id: number;
  theme_id: number;
  date: string;                   // "2026-03-15"
  time_slot: string;              // "14:00:00"
  available_slots: number | null;
  total_slots: number | null;
  status: TimeSlotStatus;
  booking_url: string | null;
  crawled_at: string;
};

export type AlertChannel = "email" | "kakao";

export type Alert = {
  id: number;
  user_id: number;
  theme_id: number;
  date: string;
  time_slot: string | null;
  channel: AlertChannel;
  is_sent: boolean;
  created_at: string;
  sent_at: string | null;
};

// API 요청 타입
export type CreateAlertRequest = {
  user_id: number;
  theme_id: number;
  date: string;
  time_slot?: string;
  channel: AlertChannel;
};
