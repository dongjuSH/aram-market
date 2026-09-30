-- 배송지 주소록(회원당 최대 10개는 서비스에서 제한, 기본 배송지는 부분 고유 인덱스로 회원당 1개 보장)
-- 회원 테이블의 주소 컬럼(postcode, address, address_detail)은 주소록으로 대체되어 제거(적용 전 데이터가 없음을 확인)

CREATE TABLE IF NOT EXISTS user_addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(20) NOT NULL,
    recipient_name VARCHAR(30) NOT NULL,
    recipient_phone VARCHAR(20) NOT NULL,
    postcode VARCHAR(10),
    address VARCHAR(200) NOT NULL,
    address_detail VARCHAR(100),
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_user_addresses_user_id ON user_addresses (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_addresses_default ON user_addresses (user_id) WHERE is_default;

ALTER TABLE users
    DROP COLUMN IF EXISTS postcode,
    DROP COLUMN IF EXISTS address,
    DROP COLUMN IF EXISTS address_detail;
