"""환경 설정. 서버의 DATABASE_URL과 동일한 DB를 사용한다."""

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: str = ".env") -> None:
    """단순 KEY=VALUE 형식만 읽고 이미 설정된 환경변수는 보존한다."""
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.replace("_", "").isalnum():
            raise ValueError(".env는 KEY=VALUE 형식이어야 합니다.")
        os.environ.setdefault(key, value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_key: str
    model: str
    user_agent: str
    timeout: int = 30
    pages_per_board: int = 2
    notices_per_board: int = 40
    analyses_per_cycle: int = 10
    poll_seconds: int = 60
    request_interval: float = 3.0

    @classmethod
    def from_env(cls):
        load_env()
        settings = cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///../server/dev.db"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            user_agent=os.getenv("CRAWLER_USER_AGENT", "GonsadajobCrawler/1.0"),
            timeout=int(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
            pages_per_board=int(os.getenv("PAGES_PER_BOARD", "2")),
            notices_per_board=int(os.getenv("NOTICES_PER_BOARD", "40")),
            analyses_per_cycle=int(os.getenv("ANALYSES_PER_CYCLE", "10")),
            poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
            request_interval=float(os.getenv("REQUEST_INTERVAL_SECONDS", "3")),
        )
        if min(settings.timeout, settings.pages_per_board, settings.notices_per_board,
               settings.analyses_per_cycle, settings.poll_seconds) < 1 or settings.request_interval < 1:
            raise ValueError("수량·시간 설정은 양수, 요청 간격은 1초 이상이어야 합니다.")
        return settings
