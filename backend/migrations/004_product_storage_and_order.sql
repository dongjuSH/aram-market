-- 상품 이미지를 Storage 경로로 전환하고 사용자별 노출순서 중복 차단

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS image_path VARCHAR(500);

ALTER TABLE public.products
    ALTER COLUMN image_data DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_products_user_display_order'
    ) THEN
        ALTER TABLE public.products
            ADD CONSTRAINT uq_products_user_display_order UNIQUE (user_id, display_order);
    END IF;
END $$;
