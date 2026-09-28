-- 기존 관리자 계정을 모두 제거하고 단일 admin 계정 전용 테이블로 축소

BEGIN;

-- 기존 관리자 삭제 전에 상품 감사 참조를 보존 가능한 NULL 값으로 전환
UPDATE public.products SET created_by_admin_id = NULL WHERE created_by_admin_id IS NOT NULL;
UPDATE public.products SET updated_by_admin_id = NULL WHERE updated_by_admin_id IS NOT NULL;
UPDATE public.product_audit_logs SET actor_admin_id = NULL WHERE actor_admin_id IS NOT NULL;

-- 사용자용으로 작성됐던 기존 계정은 향후 별도 users 도메인에서 새로 생성
DELETE FROM public.admin_accounts;

DROP INDEX IF EXISTS public.ix_admin_accounts_username;
DROP INDEX IF EXISTS public.ix_admin_accounts_nickname;
DROP INDEX IF EXISTS public.ix_admin_accounts_email;
DROP INDEX IF EXISTS public.ix_admin_accounts_status;
DROP INDEX IF EXISTS public.ix_admin_accounts_approval_status;
DROP INDEX IF EXISTS public.ix_admin_accounts_approved_by_admin_id;

ALTER TABLE public.admin_accounts
    DROP CONSTRAINT IF EXISTS admin_accounts_approved_by_admin_id_fkey,
    DROP CONSTRAINT IF EXISTS ck_admin_accounts_status,
    DROP CONSTRAINT IF EXISTS ck_admin_accounts_approval_status,
    DROP CONSTRAINT IF EXISTS ck_admin_accounts_single_username,
    DROP CONSTRAINT IF EXISTS admin_accounts_username_key,
    DROP CONSTRAINT IF EXISTS uq_admin_accounts_username,
    DROP COLUMN IF EXISTS nickname,
    DROP COLUMN IF EXISTS email,
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS approval_status,
    DROP COLUMN IF EXISTS approved_by_admin_id,
    DROP COLUMN IF EXISTS approved_at,
    DROP COLUMN IF EXISTS can_approve_accounts,
    DROP COLUMN IF EXISTS withdrawn_at,
    DROP COLUMN IF EXISTS service_policy,
    DROP COLUMN IF EXISTS privacy_policy;

ALTER TABLE public.admin_accounts
    ALTER COLUMN username SET NOT NULL,
    ALTER COLUMN password SET NOT NULL,
    ALTER COLUMN is_active SET NOT NULL,
    ALTER COLUMN login_fail_count SET NOT NULL,
    ALTER COLUMN auth_version SET NOT NULL,
    ADD CONSTRAINT ck_admin_accounts_single_username CHECK (username = 'admin'),
    ADD CONSTRAINT uq_admin_accounts_username UNIQUE (username);

-- 다음에 생성할 단일 관리자 고유번호가 1부터 시작하도록 초기화
SELECT setval(pg_get_serial_sequence('public.admin_accounts', 'id'), 1, false);

-- 관리자 탈퇴 기능 제거에 따라 기존 자정 삭제 작업과 함수를 제거
DO $$
DECLARE
    job_record RECORD;
BEGIN
    IF to_regclass('cron.job') IS NOT NULL THEN
        FOR job_record IN EXECUTE
            'SELECT jobid FROM cron.job WHERE jobname = ''purge-withdrawn-admins-midnight-kst'''
        LOOP
            PERFORM cron.unschedule(job_record.jobid);
        END LOOP;
    END IF;
END $$;

DROP FUNCTION IF EXISTS public.purge_withdrawn_admins();
DROP FUNCTION IF EXISTS public.purge_withdrawn_users();

COMMIT;
