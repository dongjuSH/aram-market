-- 관리자 계정 잠금 상태를 제거하고 접속 IP 기반 서버 제한기로 전환

BEGIN;

ALTER TABLE public.admin_accounts
    DROP COLUMN IF EXISTS login_fail_count,
    DROP COLUMN IF EXISTS locked_until;

COMMIT;
