-- 상품 복원 작업을 감사 로그의 정식 작업 유형으로 추가

ALTER TABLE public.product_audit_logs
    DROP CONSTRAINT IF EXISTS ck_product_audit_logs_action;

ALTER TABLE public.product_audit_logs
    ADD CONSTRAINT ck_product_audit_logs_action
    CHECK (action IN ('created', 'updated', 'deleted', 'restored'));
