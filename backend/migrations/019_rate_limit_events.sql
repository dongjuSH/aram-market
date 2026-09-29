-- DB 기반 요청 제한 기록(IP·이메일은 HMAC 해시로만 저장)

CREATE TABLE IF NOT EXISTS rate_limit_events (
    id SERIAL PRIMARY KEY,
    bucket VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rate_limit_events_bucket ON rate_limit_events (bucket);
CREATE INDEX IF NOT EXISTS ix_rate_limit_events_created_at ON rate_limit_events (created_at);
