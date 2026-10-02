-- 회원 이름·휴대폰 컬럼 제거: 받는 분 이름·연락처는 배송지 주소록(user_addresses)과 주문 배송지에서만 관리(개인정보 최소 수집)
-- 적용 전 apply 스크립트가 값이 저장된 회원이 없는지 확인하고, 있으면 중단한다(재실행 안전)
-- 롤백: ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(30), ADD COLUMN IF NOT EXISTS phone VARCHAR(20) (삭제된 값은 복구되지 않음)

ALTER TABLE users
    DROP COLUMN IF EXISTS name,
    DROP COLUMN IF EXISTS phone;
