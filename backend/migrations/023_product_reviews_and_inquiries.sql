-- 구매 고객 상품 후기와 로그인 고객 상품 문의(관리자 답변 포함). 탈퇴해도 내용은 남기도록 user_id는 SET NULL

CREATE TABLE IF NOT EXISTS product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_reviews_user_product UNIQUE (user_id, product_id),
    CONSTRAINT ck_product_reviews_rating CHECK (rating BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS ix_product_reviews_product_created ON product_reviews (product_id, created_at);

CREATE TABLE IF NOT EXISTS product_inquiries (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    answer TEXT,
    answered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_product_inquiries_product_created ON product_inquiries (product_id, created_at);
CREATE INDEX IF NOT EXISTS ix_product_inquiries_user_id ON product_inquiries (user_id);
