-- 약관 v1.2(서비스 이용약관·개인정보 수집 및 이용 동의, 주문 취소·환불 규칙과 취소·환불 사유 수집 추가) 시행에 맞춰 기존 활성 회원의 동의 이력을 추가
-- 대상: 이메일 인증을 마친 active 회원(탈퇴 유예 pending_deletion·withdrawn 제외), 이미 v1.2 이력이 있으면 건너뜀(재실행 안전)
-- 마케팅 동의는 v1.0을 유지하므로 추가하지 않음
-- 롤백: DELETE FROM user_policy_consents WHERE policy_version = '1.2' AND policy_type IN ('service', 'privacy') AND agreed_at = (적용 시각)

INSERT INTO user_policy_consents (user_id, policy_type, policy_version, agreed, agreed_at)
SELECT u.id, p.policy_type, '1.2', TRUE, NOW()
FROM users AS u
CROSS JOIN (VALUES ('service'), ('privacy')) AS p(policy_type)
WHERE u.status = 'active'
  AND u.email_verified_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM user_policy_consents AS c
      WHERE c.user_id = u.id AND c.policy_type = p.policy_type AND c.policy_version = '1.2'
  );
