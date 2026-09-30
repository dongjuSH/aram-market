-- 회원 이름·휴대폰·주소(가입 시 이름·휴대폰, 주소는 마이 페이지 선택 입력). 기존 회원은 NULL로 유지

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS name VARCHAR(30),
    ADD COLUMN IF NOT EXISTS phone VARCHAR(20),
    ADD COLUMN IF NOT EXISTS postcode VARCHAR(10),
    ADD COLUMN IF NOT EXISTS address VARCHAR(200),
    ADD COLUMN IF NOT EXISTS address_detail VARCHAR(100);
