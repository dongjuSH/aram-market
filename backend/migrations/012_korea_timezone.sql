-- 한국 기준 서비스의 DB 세션 기본 시간대를 Asia/Seoul로 통일
-- TIMESTAMPTZ가 가리키는 실제 순간은 변경하지 않고 조회 표현만 +09:00으로 설정한다.

DO $$
BEGIN
    EXECUTE format(
        'ALTER DATABASE %I SET timezone TO %L',
        current_database(),
        'Asia/Seoul'
    );
    EXECUTE format(
        'ALTER ROLE %I SET timezone TO %L',
        current_user,
        'Asia/Seoul'
    );
END $$;

SET TIME ZONE 'Asia/Seoul';
