-- NULL도 CHECK를 통과하므로 예약 가능 링크를 명시적으로 필수로 한다.
ALTER TABLE escape.reservation_slots ADD CONSTRAINT available_booking_link_required
 CHECK (status <> 'available' OR (booking_url IS NOT NULL AND booking_url ~ '^https?://'));
ALTER TABLE escape.schema_migrations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON escape.schema_migrations FROM PUBLIC,anon,authenticated;
