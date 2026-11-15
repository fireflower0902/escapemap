-- 서비스 기본정보와 수집 결과. Firebase 사용자 인증/기존 SQLite와 분리한다.
CREATE SCHEMA IF NOT EXISTS escape;
REVOKE ALL ON SCHEMA escape FROM PUBLIC;
REVOKE ALL ON SCHEMA escape FROM anon, authenticated;
CREATE TABLE IF NOT EXISTS escape.cafes (
 id text PRIMARY KEY,
 name text NOT NULL CHECK (length(trim(name)) > 0),
 branch_name text,
 address text NOT NULL CHECK (length(trim(address)) > 0),
 area text NOT NULL,
 is_active boolean NOT NULL DEFAULT true,
 website_url text,
 engine text,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cafes_area_active_idx ON escape.cafes(area, is_active);
CREATE TABLE IF NOT EXISTS escape.themes (
 id text PRIMARY KEY,
 cafe_id text NOT NULL REFERENCES escape.cafes(id),
 name text NOT NULL CHECK (length(trim(name)) > 0),
 is_active boolean NOT NULL DEFAULT true,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,cafe_id)
);
CREATE INDEX IF NOT EXISTS themes_cafe_active_idx ON escape.themes(cafe_id,is_active);
CREATE TABLE IF NOT EXISTS escape.reservation_slots (
 theme_id text NOT NULL,
 cafe_id text NOT NULL,
 service_date date NOT NULL,
 start_minute smallint NOT NULL CHECK (start_minute BETWEEN 0 AND 1799),
 starts_at timestamptz GENERATED ALWAYS AS ((service_date + start_minute * interval '1 minute') AT TIME ZONE 'Asia/Seoul') STORED,
 status text NOT NULL CHECK (status IN ('available','full','closed','unknown')),
 booking_url text,
 observed_at timestamptz NOT NULL,
 PRIMARY KEY(theme_id,service_date,start_minute),
 FOREIGN KEY(theme_id,cafe_id) REFERENCES escape.themes(id,cafe_id),
 CHECK (status <> 'available' OR booking_url ~ '^https?://')
);
CREATE INDEX IF NOT EXISTS slots_date_status_time_idx ON escape.reservation_slots(service_date,status,start_minute);
CREATE INDEX IF NOT EXISTS slots_cafe_date_idx ON escape.reservation_slots(cafe_id,service_date);
CREATE TABLE IF NOT EXISTS escape.cafe_date_checks (
 cafe_id text NOT NULL REFERENCES escape.cafes(id),
 service_date date NOT NULL,
 status text NOT NULL CHECK (status IN ('success','partial','failed','unimplemented')),
 last_attempt_at timestamptz NOT NULL,
 last_success_at timestamptz,
 content_hash text,
 error text,
 PRIMARY KEY(cafe_id,service_date)
);
CREATE TABLE IF NOT EXISTS escape.crawl_runs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 script text NOT NULL,
 started_at timestamptz NOT NULL,
 finished_at timestamptz,
 status text NOT NULL CHECK (status IN ('running','smoke_pass','needs_review','error','timeout')),
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS escape.crawl_results (
 run_id bigint NOT NULL REFERENCES escape.crawl_runs(id),
 cafe_id text NOT NULL REFERENCES escape.cafes(id),
 themes_count integer NOT NULL DEFAULT 0 CHECK (themes_count >= 0),
 slots_count integer NOT NULL DEFAULT 0 CHECK (slots_count >= 0),
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 PRIMARY KEY(run_id,cafe_id)
);
-- ブラウザー向け Data API には公開しない。サーバー権限でのみアクセス。
ALTER TABLE escape.cafes ENABLE ROW LEVEL SECURITY;
ALTER TABLE escape.themes ENABLE ROW LEVEL SECURITY;
ALTER TABLE escape.reservation_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE escape.cafe_date_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE escape.crawl_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE escape.crawl_results ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA escape FROM PUBLIC,anon,authenticated;
