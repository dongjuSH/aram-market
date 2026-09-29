-- 관리자 리프레시 토큰(해시 저장·회전·재사용 탐지) 테이블 추가

CREATE TABLE IF NOT EXISTS admin_refresh_tokens (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL REFERENCES admin_accounts(id) ON DELETE CASCADE,
    family_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    auth_version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_admin_refresh_tokens_admin_id ON admin_refresh_tokens (admin_id);
CREATE INDEX IF NOT EXISTS ix_admin_refresh_tokens_family ON admin_refresh_tokens (family_id);
