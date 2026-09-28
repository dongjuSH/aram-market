-- 관리자별 소유 상품을 모든 관리자가 공동 관리하는 전역 상품 카탈로그로 전환

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'user_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'created_by_user_id'
    ) THEN
        ALTER TABLE public.products RENAME COLUMN user_id TO created_by_user_id;
    END IF;
END $$;

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS updated_by_user_id INTEGER;

UPDATE public.products
SET updated_by_user_id = created_by_user_id
WHERE updated_by_user_id IS NULL;

ALTER TABLE public.products
    DROP CONSTRAINT IF EXISTS products_user_id_fkey,
    DROP CONSTRAINT IF EXISTS products_created_by_user_id_fkey,
    DROP CONSTRAINT IF EXISTS products_updated_by_user_id_fkey;

ALTER TABLE public.products
    ALTER COLUMN created_by_user_id DROP NOT NULL,
    ADD CONSTRAINT products_created_by_user_id_fkey
        FOREIGN KEY (created_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL,
    ADD CONSTRAINT products_updated_by_user_id_fkey
        FOREIGN KEY (updated_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;

DROP INDEX IF EXISTS public.ix_products_user_id;
DROP INDEX IF EXISTS public.uq_products_active_user_code;
DROP INDEX IF EXISTS public.uq_products_active_user_display_order;

CREATE INDEX IF NOT EXISTS ix_products_created_by_user_id
    ON public.products(created_by_user_id);

CREATE INDEX IF NOT EXISTS ix_products_updated_by_user_id
    ON public.products(updated_by_user_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_code
    ON public.products(code) WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_display_order
    ON public.products(display_order) WHERE status = 'active';
