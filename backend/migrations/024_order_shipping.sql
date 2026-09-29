-- 주문 배송지와 배송 상태(결제완료 → 상품준비중 → 배송중 → 배송완료). 기존 주문은 배송지 없이 결제완료 상태로 유지

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS recipient_name VARCHAR(30),
    ADD COLUMN IF NOT EXISTS recipient_phone VARCHAR(20),
    ADD COLUMN IF NOT EXISTS postcode VARCHAR(10),
    ADD COLUMN IF NOT EXISTS address VARCHAR(200),
    ADD COLUMN IF NOT EXISTS address_detail VARCHAR(100),
    ADD COLUMN IF NOT EXISTS delivery_memo VARCHAR(200),
    ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(20) NOT NULL DEFAULT 'paid',
    ADD COLUMN IF NOT EXISTS shipped_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;

ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_delivery_status;
ALTER TABLE orders ADD CONSTRAINT ck_orders_delivery_status CHECK (delivery_status IN ('paid', 'preparing', 'shipping', 'delivered'));
