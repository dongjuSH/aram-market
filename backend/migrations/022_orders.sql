-- 주문·주문 상품(가격·상품명 스냅샷)과 결제 결과. 회원·상품이 삭제돼도 거래 기록은 SET NULL로 보존

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(40) NOT NULL UNIQUE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    order_name VARCHAR(100) NOT NULL,
    total_amount BIGINT NOT NULL,
    from_cart BOOLEAN NOT NULL DEFAULT FALSE,
    payment_key VARCHAR(200) UNIQUE,
    payment_method VARCHAR(40),
    failure_message VARCHAR(300),
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_orders_status CHECK (status IN ('pending', 'paid', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_orders_user_created ON orders (user_id, created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(50) NOT NULL,
    image_url VARCHAR(500) NOT NULL DEFAULT '',
    unit_price BIGINT NOT NULL,
    quantity INTEGER NOT NULL,
    CONSTRAINT ck_order_items_quantity CHECK (quantity BETWEEN 1 AND 99)
);

CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id);
