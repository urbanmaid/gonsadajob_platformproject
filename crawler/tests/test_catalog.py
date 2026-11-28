import csv
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError
from app.http import RedirectTarget, SourceAccessError, HttpClient
from app.parsers.dankook import parse_list
from app.services.catalog import audit_catalog, canonical_url, classify, discover_links, read_catalog, select_departments, source_entries, write_reports
from app.services.pipeline import Pipeline
from tests.support import FIXTURES, URL, FakeHttp, test_database, test_settings
from tests.test_http import FakeOpener, Response

class CatalogTests(unittest.TestCase):
    def test_all_departments_and_unique_public_sources(self):
        c=read_catalog()
        self.assertEqual(len(c['departments']),117)
        self.assertEqual(len(select_departments(c,'죽전')),58)
        self.assertEqual(len(select_departments(c,'천안')),59)
        self.assertTrue(all(d['status']!='NOT_CHECKED' and d['directory_url'] for d in c['departments']))
        sources=source_entries(c['departments'])
        self.assertEqual(len(sources),161)
        self.assertEqual(len({s['list_url'] for s in sources}),161)
        self.assertNotIn('재학생1',' '.join(s['list_url'] for s in sources))

    def test_shared_majors_have_one_board(self):
        ds=select_departments(read_catalog(),department='미디어커뮤니케이션')
        self.assertGreater(len(ds),1)
        self.assertEqual(len(source_entries(ds)),1)

    def test_network_failure_does_not_abort_other_departments(self):
        c=read_catalog();c['departments']=c['departments'][:2]
        class Client:
            last_url=None;last_status=200
            def get(self,url):
                self.last_url=url
                if 'koreanlitnlang' in url:raise URLError('network')
                return (FIXTURES/'list.html').read_text()
        ds=audit_catalog(c,Client(),discover=False)['departments']
        self.assertEqual(ds[0]['status'],'NETWORK_ERROR')
        self.assertEqual(ds[1]['status'],'AVAILABLE')

    def test_shared_home_and_board_are_requested_once(self):
        c=read_catalog();c['departments']=select_departments(c,department='미디어커뮤니케이션')
        calls=[]
        class Client:
            last_url=None;last_status=200
            def get(self,url):
                calls.append(url);self.last_url=url
                return (FIXTURES/'list.html').read_text()
        audit_catalog(c,Client(),discover=False)
        self.assertEqual(len(calls),len(set(calls)))

    def test_discovery_stays_on_same_department(self):
        html='<a href="/web/test/-10">학과 공지</a><a href="/web/other/-2">공지</a><a href="https://example.com/notice">공지</a><a href="/web/test/-4?bbsMessageId=123">공지</a><a href="/web/test/-5#placeholder">공지</a>'
        self.assertEqual([x['list_url'] for x in discover_links(html,'https://cms.dankook.ac.kr/web/test')],['https://cms.dankook.ac.kr/web/test/-10'])

    def test_language_prefixed_home_keeps_department_scope(self):
        html='<a href="/ko/web/primus/notice">Notice</a><a href="/web/kor/-390">공지</a>'
        self.assertEqual([x['list_url'] for x in discover_links(html,'https://www.dankook.ac.kr/ko/web/primus/acting-filmmaking')],['https://www.dankook.ac.kr/ko/web/primus/notice'])

    def test_empty_board_differs_from_blank_page(self):
        self.assertEqual(parse_list('<div class="dku-list-body-item">내용이 없습니다.</div>',URL),[])
        self.assertEqual(classify('<h1>공지사항</h1>',URL)['status'],'BOARD_NOT_DISPLAYED')

    def test_denied_and_private_only(self):
        self.assertEqual(classify('<div id="p_p_id_dku_bbs_web_BbsPortlet_">경고 접근 거부</div>',URL)['status'],'ACCESS_DENIED')
        self.assertEqual(classify('<div class="dku-list-body-item"><a onclick="viewMessage(2, false, false)">비공개</a></div>',URL)['status'],'NO_PUBLIC_ITEMS')

    def test_blog_links_are_scoped_to_portlet(self):
        html='<a onclick="viewMessage(1, true, false)">메뉴</a><div id="p_p_id_dku_bbs_web_BbsPortlet_"><h4><a onclick="viewMessage(2, true, false)">학과 홍보</a></h4></div>'
        self.assertEqual([x.source_key for x in parse_list(html,URL)],['2'])

    def test_report_preserves_missing_home(self):
        c=read_catalog();c['departments']=select_departments(c,department='바이오소재융합공학과')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'access';write_reports(c,p)
            self.assertIn('공식 홈페이지 링크 없음',p.with_suffix('.md').read_text())
            with p.with_suffix('.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]['status'],'HOMEPAGE_NOT_LISTED')

    def test_only_observed_aliases_are_merged(self):
        self.assertEqual(canonical_url('https://law.dankook.ac.kr/-9'),canonical_url('https://law.dankook.ac.kr/web/law/-9'))
        self.assertNotEqual(canonical_url('https://cms.dankook.ac.kr/web/a/-9'),canonical_url('https://cms.dankook.ac.kr/web/b/-9'))

    def test_filter_leaves_other_pending_jobs_untouched(self):
        db,bid=test_database();self.addCleanup(db.close)
        Pipeline(db,FakeHttp(),None,test_settings()).schedule()
        p=Pipeline(db,FakeHttp(),None,test_settings(),allowed_urls=['https://cms.dankook.ac.kr/web/history/-10'])
        self.assertEqual(p.schedule(),0);self.assertIsNone(p.claim_crawl())
        self.assertEqual(db.one('SELECT status FROM crawl_logs')['status'],'PENDING')
        self.assertIsNotNone(Pipeline(db,FakeHttp(),None,test_settings(),allowed_urls=[URL]).claim_crawl())

    def test_empty_board_success_has_no_fabricated_notices(self):
        db,bid=test_database();self.addCleanup(db.close)
        client=FakeHttp();client.get=lambda *a:'<div class="dku-list-body-item">내용이 없습니다.</div>'
        result=Pipeline(db,client,None,test_settings()).run_once(analyze=False)
        self.assertEqual(result['crawl_jobs'][0]['status'],'SUCCEEDED')
        self.assertEqual(db.one('SELECT count(*) AS n FROM notices')['n'],0)

class RedirectTests(unittest.TestCase):
    def test_new_origin_robots_checked_before_redirect(self):
        class Opener(FakeOpener):
            def open(self,request,timeout):
                url=request.full_url;self.calls.append(url)
                if url=='https://www.dankook.ac.kr/robots.txt':return Response(url,'User-agent: *\nAllow: /')
                if url=='https://cms.dankook.ac.kr/robots.txt':return Response(url,'User-agent: *\nDisallow: /')
                if url=='https://www.dankook.ac.kr/moved':raise RedirectTarget('https://cms.dankook.ac.kr/target')
                raise AssertionError('disallowed request')
        opener=Opener();client=HttpClient('Test',opener=opener,sleep=lambda n:None)
        with self.assertRaises(SourceAccessError) as e:client.get('https://www.dankook.ac.kr/moved')
        self.assertEqual(e.exception.code,'ROBOTS_DENIED')
        self.assertNotIn('https://cms.dankook.ac.kr/target',opener.calls)

    def test_allowed_redirect_and_rate_limit(self):
        class Opener(FakeOpener):
            def open(self,request,timeout):
                if request.full_url.endswith('/old'):
                    self.calls.append(request.full_url);raise RedirectTarget('https://www.dankook.ac.kr/new')
                return super().open(request,timeout)
        opener=Opener();waits=[];client=HttpClient('Test',opener=opener,sleep=waits.append,clock=lambda:100)
        self.assertIn('테스트',client.get('https://www.dankook.ac.kr/old'))
        self.assertEqual(client.last_url,'https://www.dankook.ac.kr/new');self.assertTrue(waits)

    def test_login_and_redirect_loops(self):
        class Opener(FakeOpener):
            def open(self,request,timeout):
                if not request.full_url.endswith('/robots.txt'):raise RedirectTarget(request.full_url)
                return super().open(request,timeout)
        client=HttpClient('Test',opener=Opener(),sleep=lambda n:None)
        with self.assertRaises(SourceAccessError) as e:client.get('https://www.dankook.ac.kr/a')
        self.assertEqual(e.exception.code,'REDIRECT_LOOP')
        with self.assertRaises(SourceAccessError) as e:client.get('https://portal.dankook.ac.kr/proc/Login.eps')
        self.assertEqual(e.exception.code,'LOGIN_REQUIRED')
