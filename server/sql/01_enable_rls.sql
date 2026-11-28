-- =====================================================================
-- 01. 모든 테이블 RLS 켜기 + 공개 API(anon/authenticated) 접근 차단
-- =====================================================================
-- 실행 위치: Supabase 대시보드 > SQL Editor
-- 실행 시점: 서버를 Supabase에 처음 연결해 테이블이 만들어진 뒤 (AUTO_CREATE_TABLES=true)
--            테이블을 새로 추가했을 때도 다시 실행한다 (여러 번 실행해도 안전)
--
-- 왜 필요한가
--   Supabase는 public 스키마의 테이블을 REST API로 자동 공개한다.
--   프론트에 들어가는 anon key만 있으면 누구나 그 API를 부를 수 있으므로,
--   RLS를 켜지 않으면 사용자 프로필·북마크 등을 그대로 읽고 쓸 수 있다.
--
-- 이 프로젝트의 원칙
--   - 데이터는 모두 FastAPI 서버를 거쳐서만 읽고 쓴다.
--   - 서버는 테이블 소유자(postgres)로 접속하므로 RLS의 영향을 받지 않는다.
--   - 프론트는 Supabase를 로그인 용도로만 쓴다 (auth 스키마는 이 스크립트와 무관).
--   → anon/authenticated 역할에는 정책을 하나도 만들지 않는다 = 전부 거부.
-- =====================================================================

DO $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;
END $$;

-- RLS에 더해 권한 자체도 회수한다 (이중 잠금)
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

-- 앞으로 서버(postgres)가 만드는 테이블에도 자동으로 권한을 주지 않게 한다
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;

-- 확인: rls_enabled가 전부 true여야 한다
SELECT tablename, rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
