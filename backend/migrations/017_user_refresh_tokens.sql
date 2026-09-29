-- 고객 리프레시 토큰(해시 저장·회전·재사용 탐지) 테이블 추가

CREATE TABLE IF NOT EXISTS user_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    family_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    auth_version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_user_refresh_tokens_user_id ON user_refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_user_refresh_tokens_family ON user_refresh_tokens (family_id);
