-- 사용자별 상품, 확장형 카테고리 및 관련 상품 테이블 생성

CREATE TABLE IF NOT EXISTS public.product_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(40) NOT NULL,
    sort_order INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_product_categories_code UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS public.products (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL,
    category_id INTEGER NOT NULL REFERENCES public.product_categories(id),
    name VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    price BIGINT NOT NULL,
    image_path VARCHAR(500),
    image_data TEXT,
    image_name VARCHAR(255) NOT NULL,
    image_description VARCHAR(200),
    detail_html TEXT NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_products_display_order_positive CHECK (display_order >= 1),
    CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0),
    CONSTRAINT ck_products_status CHECK (status IN ('active', 'deleted'))
);

CREATE INDEX IF NOT EXISTS ix_products_user_id ON public.products(user_id);
CREATE INDEX IF NOT EXISTS ix_products_category_id ON public.products(category_id);
CREATE INDEX IF NOT EXISTS ix_products_status ON public.products(status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_user_code
    ON public.products(user_id, code) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_user_display_order
    ON public.products(user_id, display_order) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS public.product_relations (
    product_id INTEGER NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    related_product_id INTEGER NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, related_product_id),
    CONSTRAINT ck_product_relations_not_self CHECK (product_id <> related_product_id)
);

INSERT INTO public.product_categories (code, name, sort_order, is_active)
VALUES
    ('food', '식품', 1, TRUE),
    ('fashion', '패션·의류', 2, TRUE),
    ('beauty', '뷰티', 3, TRUE),
    ('digital', '디지털·가전', 4, TRUE),
    ('home', '생활·주방', 5, TRUE),
    ('furniture', '가구·인테리어', 6, TRUE),
    ('sports', '스포츠·레저', 7, TRUE),
    ('kids', '유아·완구', 8, TRUE),
    ('books', '도서·교육', 9, TRUE),
    ('pet', '반려동물', 10, TRUE)
ON CONFLICT (code) DO NOTHING;
