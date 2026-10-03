-- 주문 생성 시각과 실제 결제 승인 시도 시각을 분리해 조기 결제 조회·오판을 막음

ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_attempted_at TIMESTAMPTZ;

-- 결제 완료 주문은 승인 시각(paid_at)으로, 미확정 주문은 실제 시도 시각을 알 수 없어 마이그레이션 시각으로 채운다.
-- 미확정 주문을 배포 직후 결제사 404만으로 실패 확정하지 않도록 하루 유예가 마이그레이션 시각부터 시작된다.
UPDATE orders
SET payment_attempted_at = COALESCE(paid_at, NOW())
WHERE payment_key IS NOT NULL AND payment_attempted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_orders_payment_attempted_at ON orders (payment_attempted_at);
