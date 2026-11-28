"""개발용 샘플 데이터 넣기 (프론트 noticeData.js의 데모 공지 6건과 같은 내용).

    python scripts/seed_dev_data.py

여러 번 실행해도 같은 공지가 중복으로 생기지 않는다.
크롤러·AI 파이프라인이 붙기 전까지 프론트 연동 테스트용으로 쓴다.
"""

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")  # 한국은 서머타임이 없어 고정 오프셋으로 충분

# (데모 id, 카테고리, 제목, 요약, 게시 부서, 게시일, 마감일, 상세, 참여 조건[(type, operator, value)])
DEMO_NOTICES = [
    (1, "장학", "2026학년도 동계방학 교내 장학금 신청 안내", "장학금 신청 대상 및 제출 서류를 확인해 주세요.",
     "학생지원팀", "2026-11-27", "2026-12-10",
     "신청 자격을 확인한 후 신청서와 관련 증빙 서류를 제출해야 합니다.", []),
    (2, "행사", "소프트웨어학과 전공 역량 강화 세미나", "AI 및 소프트웨어 관련 전공 세미나 참가자를 모집합니다.",
     "소프트웨어학과", "2026-11-26", "2026-12-05",
     "세미나 참가 희망자는 신청서를 작성하여 제출해 주세요.",
     [("campus", "eq", "죽전캠퍼스"), ("department", "eq", "소프트웨어학과")]),
    (3, "기숙사", "동계방학 생활관 입사 신청 안내", "방학 중 생활관을 이용할 학생들의 입사 신청을 받습니다.",
     "생활관", "2026-11-25", "2026-12-08",
     "생활관 입사 일정과 제출 서류를 확인해 주세요.",
     [("campus", "eq", "천안캠퍼스"), ("residence", "eq", "DORM")]),
    (4, "학사", "2026학년도 2학기 기말고사 안내", "기말고사 기간 및 과목별 시험 일정을 확인해 주세요.",
     "학사팀", "2026-11-24", "2026-12-03",
     "세부 시험 일정은 각 교과목의 공지사항을 확인해야 합니다.", []),
    (5, "취업", "재학생 대상 취업 역량 강화 프로그램", "자기소개서 작성 및 면접 준비 프로그램을 진행합니다.",
     "취업지원센터", "2026-11-23", "2026-12-12",
     "취업 준비에 관심 있는 3학년 학생을 대상으로 진행합니다.", [("year", "eq", "3")]),
    (6, "행사", "2026 교내 아이디어 공모전 참가자 모집", "다양한 아이디어를 가진 재학생들의 참여를 기다립니다.",
     "학생지원팀", "2026-11-22", "2026-12-15",
     "개인 또는 팀 단위로 참가 신청서를 제출할 수 있습니다.", []),
]


def kst(day: str, hour: int = 9, minute: int = 0) -> datetime:
    """'2026-12-10' (KST) → UTC datetime"""
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, hour, minute, tzinfo=KST).astimezone(timezone.utc)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    created = 0
    with SessionLocal() as db:
        server = db.scalar(select(models.SourceServer).where(models.SourceServer.name == "단국대학교"))
        if server is None:
            server = models.SourceServer(name="단국대학교", base_url="https://www.dankook.ac.kr", interface="HTML")
            db.add(server)
            db.flush()

        boards: dict[str, models.SourceBoard] = {
            b.name: b for b in db.scalars(select(models.SourceBoard).where(models.SourceBoard.server_id == server.id))
        }

        for demo_id, category, title, summary, dept, posted, deadline, detail, reqs in DEMO_NOTICES:
            board = boards.get(dept)
            if board is None:
                board = models.SourceBoard(
                    server=server,
                    name=dept,
                    list_url=f"https://www.dankook.ac.kr/demo/{demo_id}",
                    category_hint=category,
                )
                db.add(board)
                db.flush()
                boards[dept] = board

            source_key = f"demo-{demo_id}"
            exists = db.scalar(
                select(models.Notice.id).where(
                    models.Notice.board_id == board.id, models.Notice.source_key == source_key
                )
            )
            if exists:
                continue

            body = f"{summary}\n\n{detail}"
            content_hash = hashlib.sha256(body.encode()).hexdigest()
            notice = models.Notice(
                board=board,
                source_key=source_key,
                title=title,
                content_text=body,
                source_url=f"https://www.dankook.ac.kr/demo/{demo_id}",
                published_at=kst(posted),
                content_hash=content_hash,
            )
            analysis = models.NoticeAnalysis(
                notice=notice,
                content_hash=content_hash,
                status="SUCCEEDED",
                is_current=True,
                summary_lines=[summary, detail],
                category=category,
                tags=[category],
                application_method="첨부된 신청서를 작성해 담당 부서에 제출",
                documents=["신청서"],
                model_version="seed",
                requirements=[
                    models.NoticeRequirement(logic_group=1, type=t, operator=op, value=v, evidence_text=detail)
                    for t, op, v in reqs
                ],
            )
            db.add_all([notice, analysis])
            db.flush()
            db.add(
                models.NoticeEvent(
                    notice_id=notice.id,
                    analysis_id=analysis.id,
                    event_type="APPLICATION_DEADLINE",
                    title=f"{title} 마감",
                    end_at=kst(deadline, 23, 59),
                    precision="date",
                )
            )
            created += 1
        db.commit()
    print(f"샘플 공지 {created}건 추가 (이미 있던 공지는 건너뜀)")


if __name__ == "__main__":
    main()
