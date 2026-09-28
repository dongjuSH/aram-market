-- 마이 페이지의 선택 마케팅 수신 동의 상태 저장

ALTER TABLE users
ADD COLUMN IF NOT EXISTS marketing_consent BOOLEAN NOT NULL DEFAULT FALSE;
