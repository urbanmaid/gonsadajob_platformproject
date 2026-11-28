-- =====================================================================
-- 02. 크롤러·AI 파이프라인 전용 DB 계정 (crawler)
-- =====================================================================
-- 실행 위치: Supabase 대시보드 > SQL Editor
-- 실행 순서: 01_enable_rls.sql 다음
--
-- 크롤러가 쓸 수 있는 것: 수집 대상, 수집 기록, 공지와 AI 분석 결과 테이블
-- 크롤러가 못 하는 것:   사용자 데이터(프로필·자격 정보·북마크·To-do·활동 기록) 접근
--
-- 비밀번호는 이 파일에 적지 않는다 (저장소에 올라가므로).
-- 이 스크립트를 실행한 뒤, SQL Editor에서 아래 한 줄을 따로 실행하고 저장하지 말 것:
--     ALTER ROLE crawler WITH PASSWORD '영문과숫자로된긴비밀번호';
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'crawler') THEN
        CREATE ROLE crawler LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO crawler;

-- 수집 대상: 읽기 + 마지막 수집 시각·체크포인트 갱신
GRANT SELECT, UPDATE ON public.source_servers, public.source_boards TO crawler;

-- 수집 기록: 관리자가 등록한 PENDING 작업을 가져가 상태 갱신, 정기 수집 기록 추가
GRANT SELECT, INSERT, UPDATE ON public.crawl_logs TO crawler;

-- 공지 원문과 AI 분석 결과
GRANT SELECT, INSERT, UPDATE ON public.notices, public.notice_analysis TO crawler;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.notice_requirements, public.notice_events, public.notice_attachments TO crawler;

-- RLS가 켜져 있으므로 crawler 역할이 위 테이블의 행을 볼 수 있게 정책을 연다
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'source_servers', 'source_boards', 'crawl_logs',
        'notices', 'notice_analysis', 'notice_requirements', 'notice_events', 'notice_attachments'
    ] LOOP
        EXECUTE format('DROP POLICY IF EXISTS crawler_access ON public.%I', t);
        EXECUTE format(
            'CREATE POLICY crawler_access ON public.%I FOR ALL TO crawler USING (true) WITH CHECK (true)', t
        );
    END LOOP;
END $$;

-- 확인: crawler가 가진 권한 목록
SELECT table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
FROM information_schema.role_table_grants
WHERE grantee = 'crawler'
GROUP BY table_name
ORDER BY table_name;
