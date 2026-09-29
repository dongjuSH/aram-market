-- 로그인 고객 찜 목록

CREATE TABLE IF NOT EXISTS wishlist_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_wishlist_items_user_product UNIQUE (user_id, product_id)
);

CREATE INDEX IF NOT EXISTS ix_wishlist_items_user_id ON wishlist_items (user_id);
