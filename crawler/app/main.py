"""python -m app.main으로 실행하는 크롤러 CLI."""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from app.config import Settings
from app.database import Database
from app.http import HttpClient
from app.parsers.dankook import board_url, parse_detail, parse_list
from app.services.analysis import OpenAIAnalyzer
from app.services.pipeline import Pipeline, error_code
from app.services.catalog import read_catalog, select_departments, source_entries


def emit(value):
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)


def preview(args, settings):
    if args.fixture:
        fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
        url = "https://www.dankook.ac.kr/web/kor/-390"
        links = parse_list((fixture / "list.html").read_text(encoding="utf-8"), url)
        notices = [parse_detail((fixture / "detail.html").read_text(encoding="utf-8"), links[0])]
    else:
        client = HttpClient(settings.user_agent, settings.timeout, settings.request_interval)
        links = parse_list(client.get(board_url(args.url)), args.url)
        notices = [parse_detail(client.get(link.source_url), link) for link in links[:args.limit]]
    for notice in notices:
        emit({**asdict(notice), "content_hash": notice.content_hash, "fixture": args.fixture})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="단국대 공지 수집·AI 분석 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="DB 테이블 연결·컬럼 확인 (쓰기 없음)")
    p = sub.add_parser("preview", help="수집 결과 출력 (DB 저장·AI 호출 없음)")
    p.add_argument("--url", default="https://www.dankook.ac.kr/web/kor/-390")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--fixture", action="store_true", help="네트워크 없이 합성 테스트 자료 사용")
    for command in ("run-once", "run"):
        p = sub.add_parser(command, help="수집·분석 큐 한 번 처리" if command == "run-once" else "반복 실행")
        p.add_argument("--no-schedule", action="store_true", help="정기 작업 생성 없이 관리자 요청만 처리")
        group = p.add_mutually_exclusive_group()
        group.add_argument("--crawl-only", action="store_true")
        group.add_argument("--analysis-only", action="store_true")
        p.add_argument("--max-jobs", type=int, default=10)
        p.add_argument("--campus", choices=["죽전", "천안"], help="해당 캠퍼스의 학과 공지 수집만 처리")
        p.add_argument("--department", help="학과명 부분 일치. 공유 게시판은 함께 수집")
    sub.add_parser("recover", help="중단된 RUNNING 작업을 FAILED로 마감. 재요청은 관리자 API에서")
    args = parser.parse_args(argv)
    db = None
    try:
        settings = Settings.from_env()
        if args.command == "preview":
            if not 1 <= args.limit <= 40:
                parser.error("--limit은 1~40입니다.")
            return preview(args, settings)
        db = Database(settings.database_url)
        db.check_schema()
        if args.command == "check":
            emit({"database": "sqlite" if db.sqlite else "postgresql", "common_tables": 8, "status": "OK"})
            return 0
        if hasattr(args, "max_jobs") and not 1 <= args.max_jobs <= 1000:
            parser.error("--max-jobs는 1~1000입니다.")
        allowed = None
        if getattr(args, 'campus', None) or getattr(args, 'department', None):
            if args.analysis_only:
                parser.error("학과 선택은 수집에만 적용됩니다. 분석은 전체 공통 큐로 처리하세요.")
            selected = select_departments(read_catalog(), args.campus, args.department)
            allowed = [s['list_url'] for s in source_entries(selected)]
            if not allowed:
                parser.error("선택한 학과의 활성 공개 게시판이 없습니다. 접근 점검 보고서를 확인하세요.")
            if not args.crawl_only:
                parser.error("학과 선택 실행에는 --crawl-only를 함께 지정하세요. AI 분석 큐는 전체 공통입니다.")
        with db.worker_lock():
            analyzer = OpenAIAnalyzer(settings.api_key, settings.model) if settings.api_key and not getattr(args, "crawl_only", False) else None
            pipeline = Pipeline(db, HttpClient(settings.user_agent, settings.timeout, settings.request_interval), analyzer, settings, allowed_urls=allowed)
            if args.command == "recover":
                emit(pipeline.recover())
                return 0
            while True:
                result = pipeline.run_once(scheduled=not args.no_schedule, crawl=not args.analysis_only,
                                           analyze=not args.crawl_only, max_jobs=args.max_jobs)
                emit(result)
                failed = any(j["status"] in {"FAILED", "PARTIAL"} for j in result["crawl_jobs"] + result["analysis_jobs"])
                if args.command == "run-once":
                    return 2 if failed else 0
                time.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        emit({"status": "STOPPED", "message": "작업 중 종료했다면 recover 실행 후 관리자 API에서 재요청하세요."})
        return 130
    except Exception as exc:
        emit({"status": "ERROR", "code": error_code(exc), "message": "환경 설정·DB 연결·서버 스키마·수집 정책을 확인하세요."})
        return 1
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
