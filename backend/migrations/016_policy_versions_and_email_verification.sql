-- 약관 버전·동의 이력 저장과 이메일 소유 확인 컬럼 추가

ALTER TABLE users
ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS email_verification_sent_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS user_policy_consents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    policy_type VARCHAR(20) NOT NULL,
    policy_version VARCHAR(20) NOT NULL,
    agreed BOOLEAN NOT NULL,
    agreed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_user_policy_consents_type CHECK (policy_type IN ('service', 'privacy', 'marketing'))
);

CREATE INDEX IF NOT EXISTS ix_user_policy_consents_user_type
ON user_policy_consents (user_id, policy_type);

-- 기존 회원: 가입 시점(created_at)에 동의한 것으로 보고 버전 1.0 이력을 1회만 채움
INSERT INTO user_policy_consents (user_id, policy_type, policy_version, agreed, agreed_at)
SELECT u.id, 'service', '1.0', TRUE, u.created_at
FROM users u
WHERE u.service_policy
  AND NOT EXISTS (SELECT 1 FROM user_policy_consents c WHERE c.user_id = u.id AND c.policy_type = 'service');

INSERT INTO user_policy_consents (user_id, policy_type, policy_version, agreed, agreed_at)
SELECT u.id, 'privacy', '1.0', TRUE, u.created_at
FROM users u
WHERE u.privacy_policy
  AND NOT EXISTS (SELECT 1 FROM user_policy_consents c WHERE c.user_id = u.id AND c.policy_type = 'privacy');

INSERT INTO user_policy_consents (user_id, policy_type, policy_version, agreed, agreed_at)
SELECT u.id, 'marketing', '1.0', TRUE, u.created_at
FROM users u
WHERE u.marketing_consent
  AND NOT EXISTS (SELECT 1 FROM user_policy_consents c WHERE c.user_id = u.id AND c.policy_type = 'marketing');

-- 기존 회원은 이메일 인증 도입 전 가입자이므로 로그인이 막히지 않도록 인증 완료로 처리
UPDATE users SET email_verified_at = NOW() WHERE email_verified_at IS NULL;
