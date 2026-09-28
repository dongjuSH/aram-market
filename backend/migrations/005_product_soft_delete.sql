-- 상품 원본과 이미지를 보존하는 소프트 삭제 및 활성 상품 한정 중복 방지

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE public.products
    DROP CONSTRAINT IF EXISTS uq_products_user_code,
    DROP CONSTRAINT IF EXISTS uq_products_user_display_order;

DROP INDEX IF EXISTS public.uq_products_user_code;
DROP INDEX IF EXISTS public.uq_products_user_display_order;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_status'
    ) THEN
        ALTER TABLE public.products
            ADD CONSTRAINT ck_products_status CHECK (status IN ('active', 'deleted'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_products_status ON public.products(status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_user_code
    ON public.products(user_id, code) WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_user_display_order
    ON public.products(user_id, display_order) WHERE status = 'active';
