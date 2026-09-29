-- 로그인 고객 장바구니(가격은 저장하지 않고 조회 시 현재 상품 가격 사용)

CREATE TABLE IF NOT EXISTS cart_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cart_items_user_product UNIQUE (user_id, product_id),
    CONSTRAINT ck_cart_items_quantity CHECK (quantity BETWEEN 1 AND 99)
);

CREATE INDEX IF NOT EXISTS ix_cart_items_user_id ON cart_items (user_id);
