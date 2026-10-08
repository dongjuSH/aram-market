-- 상품별 재고 수량과 주문의 재고 차감·복구 상태 추가(재실행 안전: 재고 초기값은 컬럼을 처음 만들 때 한 번만 채움)

-- 컬럼이 없을 때만 추가하고 모든 상품(노출·비노출·소프트 삭제 포함)을 100으로, 테스트용 립밤(id 16)만 2로 채운 뒤
-- 새로 등록하는 상품의 기본값은 0으로 바꾼다. 다시 실행해도 판매로 줄어든 재고를 덮어쓰지 않는다
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'stock'
    ) THEN
        ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 100;
        UPDATE products SET stock = 2 WHERE id = 16 AND name = '데일리 무향 립밤 4g';
        ALTER TABLE products ALTER COLUMN stock SET DEFAULT 0;
    END IF;
END
$$;

-- 이미 있던 stock 컬럼이 기대와 다르게 만들어졌어도 정의를 맞춤(형식 정수, NULL 불가, 새 상품 기본 0. NULL 행이 있으면 실패해 알 수 있음)
ALTER TABLE products ALTER COLUMN stock TYPE INTEGER;
ALTER TABLE products ALTER COLUMN stock SET DEFAULT 0;
ALTER TABLE products ALTER COLUMN stock SET NOT NULL;

-- 재고는 음수가 될 수 없음(조건부 차감이 실패하면 DB도 거부)
ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_stock_nonnegative;
ALTER TABLE products ADD CONSTRAINT ck_products_stock_nonnegative CHECK (stock >= 0);

-- 주문 재고 상태: NULL(차감 전·033 이전 주문), reserved(차감), released(복구), shortage(결제 확정 후 재고 부족으로 차감 못 함)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS stock_status VARCHAR(20);
ALTER TABLE orders ALTER COLUMN stock_status TYPE VARCHAR(20);
ALTER TABLE orders ALTER COLUMN stock_status DROP DEFAULT;
ALTER TABLE orders ALTER COLUMN stock_status DROP NOT NULL;
ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_stock_status;
ALTER TABLE orders ADD CONSTRAINT ck_orders_stock_status CHECK (stock_status IS NULL OR stock_status IN ('reserved', 'released', 'shortage'));
