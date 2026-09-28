-- 기존 사용자 인증 테이블을 관리자 계정·가입 승인 구조로 전환

DO $$
DECLARE
    admin_account_count BIGINT;
BEGIN
    IF to_regclass('public.admin_accounts') IS NOT NULL
        AND to_regclass('public.users') IS NOT NULL THEN
        SELECT COUNT(*) INTO admin_account_count FROM public.admin_accounts;
        IF admin_account_count = 0 THEN
            DROP TABLE public.admin_accounts;
        ELSE
            RAISE EXCEPTION 'Both users and non-empty admin_accounts tables exist';
        END IF;
    END IF;

    IF to_regclass('public.admin_accounts') IS NULL AND to_regclass('public.users') IS NOT NULL THEN
        ALTER TABLE public.users RENAME TO admin_accounts;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.admin_accounts WHERE username = 'testsign001') THEN
        RAISE EXCEPTION 'Primary admin account testsign001 was not found';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.admin_accounts
        WHERE nickname = 'admin' AND username <> 'testsign001'
    ) THEN
        RAISE EXCEPTION 'Nickname admin is already used by another account';
    END IF;
END $$;

-- 테이블명과 함께 기존 제약조건·인덱스·시퀀스 이름도 관리자 도메인에 맞춰 정리
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_pkey')
        AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'admin_accounts_pkey') THEN
        ALTER TABLE public.admin_accounts RENAME CONSTRAINT users_pkey TO admin_accounts_pkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_key')
        AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'admin_accounts_username_key') THEN
        ALTER TABLE public.admin_accounts RENAME CONSTRAINT users_username_key TO admin_accounts_username_key;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_nickname_key')
        AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'admin_accounts_nickname_key') THEN
        ALTER TABLE public.admin_accounts RENAME CONSTRAINT users_nickname_key TO admin_accounts_nickname_key;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_email_key')
        AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'admin_accounts_email_key') THEN
        ALTER TABLE public.admin_accounts RENAME CONSTRAINT users_email_key TO admin_accounts_email_key;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_status')
        AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_admin_accounts_status') THEN
        ALTER TABLE public.admin_accounts RENAME CONSTRAINT ck_users_status TO ck_admin_accounts_status;
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.ix_users_username') IS NOT NULL
        AND to_regclass('public.ix_admin_accounts_username') IS NULL THEN
        ALTER INDEX public.ix_users_username RENAME TO ix_admin_accounts_username;
    END IF;
    IF to_regclass('public.ix_users_nickname') IS NOT NULL
        AND to_regclass('public.ix_admin_accounts_nickname') IS NULL THEN
        ALTER INDEX public.ix_users_nickname RENAME TO ix_admin_accounts_nickname;
    END IF;
    IF to_regclass('public.ix_users_email') IS NOT NULL
        AND to_regclass('public.ix_admin_accounts_email') IS NULL THEN
        ALTER INDEX public.ix_users_email RENAME TO ix_admin_accounts_email;
    END IF;
    IF to_regclass('public.ix_users_status') IS NOT NULL
        AND to_regclass('public.ix_admin_accounts_status') IS NULL THEN
        ALTER INDEX public.ix_users_status RENAME TO ix_admin_accounts_status;
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.users_id_seq') IS NOT NULL
        AND to_regclass('public.admin_accounts_id_seq') IS NULL THEN
        ALTER SEQUENCE public.users_id_seq RENAME TO admin_accounts_id_seq;
    END IF;
END $$;

ALTER TABLE public.admin_accounts
    ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS approved_by_admin_id INTEGER,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS can_approve_accounts BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.admin_accounts
    DROP CONSTRAINT IF EXISTS ck_users_role,
    DROP CONSTRAINT IF EXISTS ck_admin_accounts_approval_status,
    DROP CONSTRAINT IF EXISTS admin_accounts_approved_by_admin_id_fkey;

ALTER TABLE public.admin_accounts
    ADD CONSTRAINT ck_admin_accounts_approval_status
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    ADD CONSTRAINT admin_accounts_approved_by_admin_id_fkey
        FOREIGN KEY (approved_by_admin_id) REFERENCES public.admin_accounts(id) ON DELETE SET NULL;

-- 마이그레이션 이전 계정은 기존 접속·탈퇴 테스트가 중단되지 않도록 승인 상태 보존
UPDATE public.admin_accounts
SET approval_status = 'approved',
    approved_at = COALESCE(approved_at, NOW())
WHERE username IN ('testsign001', 'testsign002', 'testsign003');

-- 최초 승인 관리자 지정 및 화면 표시명 변경
UPDATE public.admin_accounts
SET nickname = 'admin',
    can_approve_accounts = TRUE
WHERE username = 'testsign001';

UPDATE public.admin_accounts
SET can_approve_accounts = FALSE
WHERE username <> 'testsign001';

WITH primary_admin AS (
    SELECT id FROM public.admin_accounts WHERE username = 'testsign001'
)
UPDATE public.admin_accounts
SET approved_by_admin_id = primary_admin.id
FROM primary_admin
WHERE admin_accounts.approved_by_admin_id IS NULL
  AND admin_accounts.approval_status = 'approved';

CREATE INDEX IF NOT EXISTS ix_admin_accounts_approval_status
    ON public.admin_accounts(approval_status);

CREATE INDEX IF NOT EXISTS ix_admin_accounts_approved_by_admin_id
    ON public.admin_accounts(approved_by_admin_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'created_by_user_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'created_by_admin_id'
    ) THEN
        ALTER TABLE public.products RENAME COLUMN created_by_user_id TO created_by_admin_id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'updated_by_user_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'updated_by_admin_id'
    ) THEN
        ALTER TABLE public.products RENAME COLUMN updated_by_user_id TO updated_by_admin_id;
    END IF;

    IF to_regclass('public.product_audit_logs') IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'product_audit_logs' AND column_name = 'actor_user_id'
        )
        AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'product_audit_logs' AND column_name = 'actor_admin_id'
        ) THEN
        ALTER TABLE public.product_audit_logs RENAME COLUMN actor_user_id TO actor_admin_id;
    END IF;
END $$;

ALTER TABLE public.products
    DROP CONSTRAINT IF EXISTS products_created_by_user_id_fkey,
    DROP CONSTRAINT IF EXISTS products_updated_by_user_id_fkey,
    DROP CONSTRAINT IF EXISTS products_created_by_admin_id_fkey,
    DROP CONSTRAINT IF EXISTS products_updated_by_admin_id_fkey;

ALTER TABLE public.products
    ADD CONSTRAINT products_created_by_admin_id_fkey
        FOREIGN KEY (created_by_admin_id) REFERENCES public.admin_accounts(id) ON DELETE SET NULL,
    ADD CONSTRAINT products_updated_by_admin_id_fkey
        FOREIGN KEY (updated_by_admin_id) REFERENCES public.admin_accounts(id) ON DELETE SET NULL;

DROP INDEX IF EXISTS public.ix_products_created_by_user_id;
DROP INDEX IF EXISTS public.ix_products_updated_by_user_id;

CREATE INDEX IF NOT EXISTS ix_products_created_by_admin_id
    ON public.products(created_by_admin_id);

CREATE INDEX IF NOT EXISTS ix_products_updated_by_admin_id
    ON public.products(updated_by_admin_id);

DO $$
BEGIN
    IF to_regclass('public.product_audit_logs') IS NOT NULL THEN
        ALTER TABLE public.product_audit_logs
            DROP CONSTRAINT IF EXISTS product_audit_logs_actor_user_id_fkey,
            DROP CONSTRAINT IF EXISTS product_audit_logs_actor_admin_id_fkey;

        ALTER TABLE public.product_audit_logs
            ADD CONSTRAINT product_audit_logs_actor_admin_id_fkey
                FOREIGN KEY (actor_admin_id) REFERENCES public.admin_accounts(id) ON DELETE SET NULL;

        DROP INDEX IF EXISTS public.ix_product_audit_logs_actor_user_id;
        CREATE INDEX IF NOT EXISTS ix_product_audit_logs_actor_admin_id
            ON public.product_audit_logs(actor_admin_id);
    END IF;
END $$;
