"""파이프라인 내부 전달 자료. DB 테이블은 server/app/models.py가 기준이다."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Attachment:
    file_name: str
    file_url: str
    file_type: str | None = None


@dataclass(frozen=True)
class NoticeLink:
    source_key: str
    title: str
    source_url: str
    published_at: datetime | None = None


@dataclass
class CollectedNotice:
    source_key: str
    title: str
    source_url: str
    content_text: str
    published_at: datetime | None = None
    attachments: list[Attachment] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        # 조회수·목록 순서는 제외한다. 제목/본문/첨부 URL/이미지 변경은 재분석한다.
        content = {
            "title": " ".join(self.title.split()),
            "text": " ".join(self.content_text.split()),
            "attachments": sorted((asdict(a) for a in self.attachments), key=lambda a: a["file_url"]),
            "images": sorted(set(self.image_urls)),
        }
        return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
