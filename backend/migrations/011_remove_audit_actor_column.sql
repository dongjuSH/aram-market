-- 단일 관리자 구조에서 중복되는 감사 로그 작업자 참조 제거

BEGIN;

ALTER TABLE public.product_audit_logs
    DROP CONSTRAINT IF EXISTS product_audit_logs_actor_admin_id_fkey;

DROP INDEX IF EXISTS public.ix_product_audit_logs_actor_admin_id;

ALTER TABLE public.product_audit_logs
    DROP COLUMN IF EXISTS actor_admin_id;

COMMIT;
