-- 단일 관리자 구조에서 중복되는 상품 등록·수정 관리자 참조 제거

BEGIN;

ALTER TABLE public.products
    DROP CONSTRAINT IF EXISTS products_created_by_admin_id_fkey,
    DROP CONSTRAINT IF EXISTS products_updated_by_admin_id_fkey;

DROP INDEX IF EXISTS public.ix_products_created_by_admin_id;
DROP INDEX IF EXISTS public.ix_products_updated_by_admin_id;

ALTER TABLE public.products
    DROP COLUMN IF EXISTS created_by_admin_id,
    DROP COLUMN IF EXISTS updated_by_admin_id;

COMMIT;
