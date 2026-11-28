"""단국대 dku_bbs_web_BbsPortlet 파서 (2026-11-29 일반공지 DOM 확인)."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from app.models import Attachment, CollectedNotice, NoticeLink

PARSER_VERSION = "dku_bbs_v1"
PREFIX = "_dku_bbs_web_BbsPortlet_"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section"}


class ParseError(ValueError):
    pass


class BoardAccessError(ParseError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def text(self):
        if self.tag in {"script", "style", "noscript"}:
            return ""
        text = "".join(c.text() if isinstance(c, Node) else c for c in self.children)
        return text + ("\n" if self.tag in BLOCK else "")


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, text):
        self.stack[-1].children.append(text)


def clean(text):
    return "\n".join(line for part in text.splitlines() if (line := " ".join(part.split())))


def parse_date(text):
    found = re.search(r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})", text)
    if not found:
        return None
    try:
        # 현재 한국 공지는 UTC+09:00. Windows의 별도 tzdata 설치 없이 동일하게 처리한다.
        return datetime(*map(int, found.groups()), tzinfo=timezone(timedelta(hours=9), "Asia/Seoul"))
    except ValueError:
        return None


def board_url(url, *, page=1, message_id=None):
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    query.update({"p_p_id": ["dku_bbs_web_BbsPortlet"], "p_p_lifecycle": ["0"],
                  "p_p_state": ["normal"], "p_p_mode": ["view"],
                  PREFIX + "cur": [str(page)], PREFIX + "orderBy": ["createDate"],
                  PREFIX + "action": ["view_message" if message_id else "view"]})
    query.pop(PREFIX + "bbsMessageId", None)
    if message_id:
        query[PREFIX + "bbsMessageId"] = [str(message_id)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def parse_list(html, list_url):
    root = Document(html).root
    rows = [n for n in root.walk() if n.has_class("dku-list-body-item")]
    portlet = next((n for n in root.walk() if n.attrs.get("id") == "p_p_id_dku_bbs_web_BbsPortlet_"), None)
    if not rows:
        if portlet and "접근 거부" in portlet.text():
            raise BoardAccessError("ACCESS_DENIED")
        # 물리학과 홍보 게시판처럼 블로그형 목록도 동일한 공개 읽기 함수를 사용한다.
        if portlet and any(n.tag == "a" and "viewMessage(" in n.attrs.get("onclick", "") for n in portlet.walk()):
            rows = [portlet]
        else:
            raise ParseError("공지 목록 구조가 없습니다. 로그인/차단 응답 또는 파서 변경을 확인하세요.")
    links = {}
    private = False
    for row in rows:
        for anchor in row.walk():
            if anchor.tag != "a":
                continue
            matched = re.search(r"(?:_dku_bbs_web_BbsPortlet_)?viewMessage\(\s*(\d+)\s*,\s*(true|false)\s*,\s*(true|false)",
                                anchor.attrs.get("onclick", ""))
            href = anchor.attrs.get("href", "")
            key = parse_qs(urlsplit(href).query).get(PREFIX + "bbsMessageId", [None])[0]
            if matched:
                # 사이트가 공개 읽기 불가/비밀글로 표시한 게시글은 요청하지 않는다.
                if matched[2] != "true" or matched[3] == "true":
                    private = True
                    continue
                key = matched[1]
            if not key or not str(key).isdigit():
                continue
            title = clean(anchor.attrs.get("title") or anchor.text())
            if title:
                links[str(key)] = NoticeLink(str(key), title[:500], board_url(list_url, message_id=key), parse_date(row.text()))
    if not links:
        if private:
            raise BoardAccessError("NO_PUBLIC_ITEMS")
        if any("내용이 없습니다." in n.text() or "게시물이 없습니다" in n.text() for n in rows):
            return []
        raise ParseError("읽을 수 있는 공지 링크가 없습니다. 빈 결과를 정상 수집으로 처리하지 않습니다.")
    return list(links.values())


def parse_detail(html, link):
    root = Document(html).root
    table = next((n for n in root.walk() if n.has_class("dku-bbs-view_message-inner")), None)
    if table is None:
        raise ParseError("공지 상세 표가 없습니다.")
    body = next((n for n in table.walk() if n.has_class("r_cont")), None)
    title = next((n for n in table.walk() if n.tag == "th" and n.attrs.get("colspan") == "2"), None)
    if body is None or title is None or not clean(title.text()):
        raise ParseError("제목/본문 선택자가 변경되었습니다.")
    attachments = {}
    published = link.published_at
    for row in (n for n in table.walk() if n.tag == "tr"):
        header = next((n for n in row.children if isinstance(n, Node) and n.tag == "th"), None)
        if not header or header.attrs.get("colspan"):
            continue
        label = header.text()
        if "날짜" in label:
            published = parse_date(row.text()) or published
        if "파일첨부" in label:
            for node in row.walk():
                if node.tag == "a" and node.attrs.get("href"):
                    url = urljoin(link.source_url, node.attrs["href"])
                    name = clean(node.text())
                    if urlsplit(url).scheme in {"http", "https"} and name:
                        suffix = name.rsplit(".", 1)[-1].lower() if "." in name else None
                        attachments[url] = Attachment(name[:300], url, suffix[:20] if suffix else None)
    images = [urljoin(link.source_url, n.attrs["src"]) for n in body.walk()
              if n.tag == "img" and n.attrs.get("src")]
    text = clean(body.text())
    if not text and not images and not attachments:
        raise ParseError("빈 본문은 저장하지 않습니다.")
    return CollectedNotice(link.source_key, clean(title.text())[:500], link.source_url,
                           text, published, list(attachments.values()), images)
