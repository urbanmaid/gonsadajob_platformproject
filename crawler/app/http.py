"""공개 단국대 게시판 GET: robots.txt, 속도 제한, 제한된 재시도."""

import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser


class SourceAccessError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class RedirectTarget(ValueError):
    def __init__(self, url):
        self.url = url
        super().__init__("SOURCE_REDIRECT")


def validate_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "dankook.ac.kr" or host.endswith(".dankook.ac.kr") or host == "ai-architecture-website.pages.dev"):
        raise ValueError("HTTPS 단국대학교 공개 주소만 수집할 수 있습니다.")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("사용자정보/비표준 포트가 있는 URL은 허용하지 않습니다.")
    if host == "portal.dankook.ac.kr" or "/sso/" in parsed.path.lower() or "login" in parsed.path.lower():
        raise SourceAccessError("LOGIN_REQUIRED")
    return parsed


class CheckedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        # urllib는 따라가지 않는다. get()이 이동 목적지 robots를 검증한 뒤 요청한다.
        raise RedirectTarget(newurl)


class HttpClient:
    def __init__(self, user_agent, timeout=30, interval=3.0, opener=None, clock=time.monotonic, sleep=time.sleep):
        self.user_agent, self.timeout, self.interval = user_agent, timeout, interval
        self.opener = opener or build_opener(CheckedRedirect())
        self.clock, self.sleep = clock, sleep
        self.last_request, self.robots = {}, {}
        self.last_status = None
        self.last_url = None

    def _read(self, url, interval, limit=5_000_000):
        host = validate_url(url).hostname
        for attempt in range(3):
            wait = interval - (self.clock() - self.last_request.get(host, -interval))
            if wait > 0:
                self.sleep(wait)
            self.last_request[host] = self.clock()
            try:
                with self.opener.open(Request(url, headers={"User-Agent": self.user_agent,
                                                           "Accept": "text/html,text/plain"}), timeout=self.timeout) as response:
                    validate_url(response.url)
                    self.last_status = response.status
                    self.last_url = response.url
                    data = response.read(limit + 1)
                    if len(data) > limit:
                        raise ValueError("응답 크기가 제한을 초과했습니다.")
                    charset = response.headers.get_content_charset() or "utf-8"
                    return data.decode(charset, errors="replace")
            except HTTPError as exc:
                self.last_status = exc.code
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    exc.close()
                    raise
                retry_after = exc.headers.get("Retry-After", "")
                delay = min(60, int(retry_after)) if retry_after.isdigit() else 2 ** (attempt + 1)
                exc.close()
                self.sleep(delay)
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise
                self.sleep(2 ** (attempt + 1))

    def get(self, url, rate_limit_per_minute=None, _visited=None):
        visited = set() if _visited is None else set(_visited)
        if url in visited or len(visited) >= 6:
            raise SourceAccessError("REDIRECT_LOOP")
        visited.add(url)
        # 한글 경로가 들어온 설정도 Request에서 ASCII URL로 전송한다.
        p = urlsplit(url)
        url = urlunsplit((p.scheme, p.netloc, quote(p.path, safe="/%:@-._~"), p.query, ""))
        parts = validate_url(url)
        interval = max(self.interval, 60 / rate_limit_per_minute) if rate_limit_per_minute else self.interval
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        cached = self.robots.get(origin)
        if not cached or self.clock() - cached[0] > 3600:
            robots = RobotFileParser(origin + "/robots.txt")
            try:
                text = self._read(origin + "/robots.txt", interval, 500_000)
            except RedirectTarget as exc:
                # robots가 다른 곳으로 이동하면 임의 허용하지 않고 운영자가 확인한다.
                raise SourceAccessError("ROBOTS_REDIRECT") from exc
            except HTTPError as exc:
                if exc.code not in (404, 410):
                    raise SourceAccessError("ROBOTS_UNAVAILABLE") from exc
                text = "User-agent: *\nAllow: /"
            if "<html" in text.lower():
                raise SourceAccessError("ROBOTS_INVALID")
            robots.parse(text.splitlines())
            self.robots[origin] = (self.clock(), robots)
        robots = self.robots[origin][1]
        if not robots.can_fetch(self.user_agent, url):
            raise SourceAccessError("ROBOTS_DENIED")
        delay = robots.crawl_delay(self.user_agent) or robots.crawl_delay("*") or 0
        rate = robots.request_rate(self.user_agent) or robots.request_rate("*")
        if rate and rate.requests:
            interval = max(interval, rate.seconds / rate.requests)
        try:
            return self._read(url, max(interval, delay))
        except RedirectTarget as exc:
            return self.get(urljoin(url, exc.url), rate_limit_per_minute, visited)
