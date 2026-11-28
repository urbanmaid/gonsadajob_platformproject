import io
import unittest
from email.message import Message
from urllib.error import HTTPError
from urllib.request import Request

from app.http import CheckedRedirect, HttpClient, validate_url


class Response(io.BytesIO):
    def __init__(self, url, body):
        super().__init__(body.encode())
        self.url, self.status = url, 200
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"


class FakeOpener:
    def __init__(self, robots="User-agent: *\nAllow: /", fail_once=False):
        self.robots, self.calls, self.fail_once = robots, [], fail_once

    def open(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return Response(url, self.robots)
        if self.fail_once:
            self.fail_once = False
            headers = Message()
            headers["Retry-After"] = "2"
            raise HTTPError(url, 429, "rate", headers, None)
        return Response(url, "<html>테스트</html>")


class HttpTests(unittest.TestCase):
    def test_url_allowlist(self):
        validate_url("https://www.dankook.ac.kr/web/kor/-390")
        for url in ("http://www.dankook.ac.kr", "https://dankook.ac.kr.evil.example/x", "https://127.0.0.1", "https://name:password@www.dankook.ac.kr", "https://www.dankook.ac.kr:8000"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    def test_robots_disallow_prevents_page_request(self):
        opener = FakeOpener("User-agent: *\nDisallow: /")
        client = HttpClient("TestCrawler", opener=opener, sleep=lambda n: None)
        with self.assertRaises(ValueError):
            client.get("https://www.dankook.ac.kr/web/kor/-390")
        self.assertEqual(len(opener.calls), 1)

    def test_robots_cache_and_retry_after(self):
        opener, waits = FakeOpener(fail_once=True), []
        client = HttpClient("TestCrawler", opener=opener, sleep=waits.append, clock=lambda: 100)
        self.assertIn("테스트", client.get("https://www.dankook.ac.kr/web/kor/-390"))
        client.get("https://www.dankook.ac.kr/web/kor/-390")
        self.assertEqual(sum(url.endswith("robots.txt") for url in opener.calls), 1)
        self.assertIn(2, waits)

    def test_unchecked_redirect_is_rejected(self):
        with self.assertRaises(ValueError):
            CheckedRedirect().redirect_request(Request("https://www.dankook.ac.kr/a"), None, 302, "", {}, "https://www.dankook.ac.kr/b")
