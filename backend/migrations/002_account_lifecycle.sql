-- 탈퇴 유예·보관 정책 및 비밀번호 재설정 토큰 무효화용 컬럼 추가

ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0;

UPDATE users
SET status = 'active'
WHERE status IS NULL;

CREATE INDEX IF NOT EXISTS ix_users_status ON users (status);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_status'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT ck_users_status
      CHECK (status IN ('active', 'pending_deletion', 'withdrawn'));
  END IF;
END $$;
