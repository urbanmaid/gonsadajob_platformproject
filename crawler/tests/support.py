import json
from pathlib import Path

from app.config import Settings
from app.database import Database
from app.parsers.dankook import parse_detail, parse_list

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.dankook.ac.kr/web/kor/-390"


def fixture_notice():
    link = parse_list((FIXTURES / "list.html").read_text(encoding="utf-8"), URL)[0]
    return parse_detail((FIXTURES / "detail.html").read_text(encoding="utf-8"), link)


def fixture_analysis():
    return json.loads((FIXTURES / "analysis.json").read_text(encoding="utf-8"))


def test_database():
    db = Database("sqlite:///:memory:")
    db.connection.executescript((FIXTURES / "schema.sql").read_text(encoding="utf-8"))
    now, server_id, board_id = db.timestamp(), db.key(), db.key()
    # 실제 등록은 관리자 API만 한다. 테스트 DB에만 초기 자료를 넣는다.
    db.insert("source_servers", id=server_id, name="테스트 단국대", base_url="https://www.dankook.ac.kr",
              interface="HTML", location=None, rate_limit_per_minute=20, crawl_allowed=True,
              access_restricted=False, created_at=now, updated_at=now)
    db.insert("source_boards", id=board_id, server_id=server_id, name="합성 공지", list_url=URL,
              category_hint="일반", crawl_interval_minutes=60, parser_version="dku_bbs_v1", is_active=True,
              last_success_at=None, checkpoint=None, created_at=now, updated_at=now)
    return db, board_id


def test_settings():
    return Settings("sqlite:///:memory:", "", "fixture", "TestCrawler", pages_per_board=1)


class FakeHttp:
    last_status = None

    def get(self, url, rate_limit_per_minute=None):
        self.last_status = 200
        filename = "detail.html" if "bbsMessageId=" in url else "list.html"
        return (FIXTURES / filename).read_text(encoding="utf-8")


class FakeAnalyzer:
    model = "fixture-only-not-a-real-model"

    def analyze(self, notice, attachments):
        from app.schemas import validate_analysis
        return validate_analysis(fixture_analysis(), notice, bool(attachments))
