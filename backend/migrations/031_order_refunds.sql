-- 주문 전액 환불(토스 결제 취소)과 고객 취소 요청·관리자 승인/거절 기록을 위한 상태·컬럼 추가(재실행 안전)

-- 환불 확인 중(refunding)·환불 완료(refunded) 상태 허용(허용값 확장이라 기존 코드와 호환)
ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_status;
ALTER TABLE orders ADD CONSTRAINT ck_orders_status CHECK (status IN ('pending', 'paid', 'failed', 'refunding', 'refunded'));

-- 고객 취소 요청(상품준비중 주문만, 주문당 1회)과 관리자 승인·거절 기록
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancel_request_status VARCHAR(20);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancel_request_reason_code VARCHAR(30);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancel_request_reason_detail VARCHAR(100);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancel_rejected_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancel_reject_reason VARCHAR(200);

-- 환불 처리 기록(처리 주체·사유·결제사 취소 시도 횟수와 결과)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_actor VARCHAR(20);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_reason_code VARCHAR(30);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_reason_detail VARCHAR(100);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_attempted_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_transaction_key VARCHAR(64);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_failure_message VARCHAR(300);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_delivery_status VARCHAR(20);

ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cancel_request_status;
ALTER TABLE orders ADD CONSTRAINT ck_orders_cancel_request_status CHECK (cancel_request_status IS NULL OR cancel_request_status IN ('requested', 'approved', 'rejected'));
ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cancel_request_reason_code;
ALTER TABLE orders ADD CONSTRAINT ck_orders_cancel_request_reason_code CHECK (
    cancel_request_reason_code IS NULL
    OR cancel_request_reason_code IN ('change_of_mind', 'wrong_order', 'delivery_delay', 'reorder', 'other')
);
ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_refund_actor;
ALTER TABLE orders ADD CONSTRAINT ck_orders_refund_actor CHECK (refund_actor IS NULL OR refund_actor IN ('customer', 'admin'));
ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_refund_reason_code;
ALTER TABLE orders ADD CONSTRAINT ck_orders_refund_reason_code CHECK (
    refund_reason_code IS NULL
    OR refund_reason_code IN (
        'change_of_mind', 'wrong_order', 'delivery_delay', 'reorder',
        'customer_request', 'out_of_stock', 'undeliverable', 'other'
    )
);
ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_refund_attempt_count;
ALTER TABLE orders ADD CONSTRAINT ck_orders_refund_attempt_count CHECK (refund_attempt_count >= 0);

-- 환불 보정 작업(환불 확인 중 주문 조회)과 관리자 '취소 요청' 탭용 부분 인덱스
CREATE INDEX IF NOT EXISTS ix_orders_refunding_attempted_at ON orders (refund_attempted_at) WHERE status = 'refunding';
CREATE INDEX IF NOT EXISTS ix_orders_cancel_requested ON orders (cancel_requested_at) WHERE cancel_request_status = 'requested';
