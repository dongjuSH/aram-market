-- Storage 전환이 완료된 상품의 레거시 Base64 이미지 컬럼 제거

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.products WHERE image_path IS NULL) THEN
        RAISE EXCEPTION 'image_path가 없는 상품이 있어 image_data 컬럼을 제거할 수 없습니다.';
    END IF;
END $$;

ALTER TABLE public.products
    ALTER COLUMN image_path SET NOT NULL,
    DROP COLUMN IF EXISTS image_data;
