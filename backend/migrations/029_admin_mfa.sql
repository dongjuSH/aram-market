-- 관리자 TOTP 2단계 인증(MFA): 암호화한 비밀값, 등록 시각, 마지막으로 사용한 시간 단계(코드 재사용 방지), 복구 코드 해시 목록

ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS mfa_secret_encrypted TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS mfa_enabled_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS mfa_last_used_step BIGINT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS mfa_recovery_code_hashes JSONB NOT NULL DEFAULT '[]'::jsonb;
