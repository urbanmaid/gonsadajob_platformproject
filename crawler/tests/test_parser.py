import unittest
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

from app.parsers.dankook import NoticeLink, ParseError, board_url, parse_detail, parse_list
from tests.support import FIXTURES, URL, fixture_notice


class ParserTests(unittest.TestCase):
    def test_list_uses_message_id_and_skips_private(self):
        links = parse_list((FIXTURES / "list.html").read_text(), URL)
        self.assertEqual([l.source_key for l in links], ["900001"])
        self.assertIn("bbsMessageId=900001", links[0].source_url)
        self.assertEqual(links[0].title, "소프트웨어 실습 프로그램 안내")

    def test_detail_excludes_navigation_scripts_and_views(self):
        notice = fixture_notice()
        self.assertNotIn("본문에 들어가면", notice.content_text)
        self.assertNotIn("스크립트", notice.content_text)
        self.assertNotIn("1234", notice.content_text)
        self.assertEqual(notice.attachments[0].file_url, "https://www.dankook.ac.kr/documents/example.pdf")
        self.assertEqual(notice.published_at.utcoffset().total_seconds(), 32400)

    def test_missing_structure_is_an_error(self):
        with self.assertRaises(ParseError):
            parse_list("<html>로그인</html>", URL)
        with self.assertRaises(ParseError):
            parse_detail("<html>로그인</html>", NoticeLink("1", "제목", URL))

    def test_hash_ignores_whitespace_but_tracks_title_attachments_and_images(self):
        a = fixture_notice()
        self.assertEqual(a.content_hash, replace(a, content_text=a.content_text.replace(" ", "  ")).content_hash)
        for changed in (replace(a, title="수정"), replace(a, attachments=[]), replace(a, image_urls=[URL + "/x.jpg"])):
            self.assertNotEqual(a.content_hash, changed.content_hash)

    def test_pagination_drops_detail_id_and_preserves_board_parameters(self):
        url = board_url(URL + "?boardId=7&_dku_bbs_web_BbsPortlet_bbsMessageId=9", page=2)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["boardId"], ["7"])
        self.assertEqual(query["_dku_bbs_web_BbsPortlet_cur"], ["2"])
        self.assertNotIn("_dku_bbs_web_BbsPortlet_bbsMessageId", query)

    def test_image_only_notice_is_preserved_for_review(self):
        html = '<table class="dku-bbs-view_message-inner"><tr><th colspan="2">그림 공지</th></tr><tr><td class="r_cont"><img src="/poster.png"></td></tr></table>'
        notice = parse_detail(html, NoticeLink("1", "그림 공지", URL))
        self.assertEqual(notice.content_text, "")
        self.assertEqual(len(notice.image_urls), 1)
