-- Supabase SQL Editor 1회 실행용 인증 스키마 마이그레이션
-- 운영 데이터 실행 전 백업 및 닉네임 중복 여부 확인 필요

ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;

UPDATE users
SET username = CONCAT('user_', id)
WHERE username IS NULL;

UPDATE users
SET username = LOWER(username);

UPDATE users
SET nickname = CONCAT('사용자', id)
WHERE nickname IS NULL;

ALTER TABLE users ALTER COLUMN username SET NOT NULL;
ALTER TABLE users ALTER COLUMN nickname SET NOT NULL;
ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(20);
ALTER TABLE users ALTER COLUMN nickname TYPE VARCHAR(10);
ALTER TABLE users ALTER COLUMN email TYPE VARCHAR(254);
ALTER TABLE users ALTER COLUMN password TYPE VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_nickname ON users (nickname);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
