"""관리자 API를 통해 config/sources.json을 등록한다. crawler DB 계정은 INSERT 권한이 없다."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_env
from app.http import validate_url
from app.services.catalog import canonical_url, read_catalog, select_departments, source_entries


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("관리자 API 주소가 이동했습니다. API_BASE_URL을 확인하세요.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="관리자 API로 실제 등록. 생략하면 JSON만 출력")
    parser.add_argument("--config", help="생략하면 기존 일반공지 + 모든 공개 학과 공지")
    parser.add_argument("--campus", choices=["죽전", "천안"])
    parser.add_argument("--department", help="학과명 부분 일치")
    args = parser.parse_args()
    load_env()
    if args.config and (args.campus or args.department):
        parser.error("--config와 학과 선택 옵션은 함께 사용할 수 없습니다.")
    if args.config:
        sources = json.loads(Path(args.config).read_text(encoding="utf-8"))
    else:
        sources = source_entries(select_departments(read_catalog(), args.campus, args.department))
        if not (args.campus or args.department):
            sources = json.loads((Path(__file__).resolve().parents[1]/'config/sources.json').read_text(encoding='utf-8')) + sources
    if not sources:
        parser.error("등록할 공개 게시판이 없습니다.")
    for source in sources:
        validate_url(source["list_url"])
    if not args.apply:
        print(json.dumps(sources, ensure_ascii=False, indent=2))
        return 0
    token = os.getenv("ADMIN_ACCESS_TOKEN", "")
    base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
    parts = urlsplit(base)
    if parts.username or parts.password or parts.query or parts.fragment or (parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"})):
        raise ValueError("관리자 API는 로컬 HTTP 또는 HTTPS 주소를 사용하세요.")
    if not token:
        raise ValueError("ADMIN_ACCESS_TOKEN을 환경변수 또는 .env에 설정하세요.")
    opener = build_opener(NoRedirect())

    def request(path, body=None):
        req = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with opener.open(req, timeout=30) as response:
            return json.load(response)

    existing, page = [], 1
    while True:
        data = request(f"/admin/sources?page={page}&limit=100")
        existing.extend(data["items"])
        if len(existing) >= data["total"] or not data["items"]:
            break
        page += 1
    for source in sources:
        matches = [s for s in existing if canonical_url(s["list_url"]) == canonical_url(source["list_url"])]
        if matches:
            print(json.dumps({"status": "SKIPPED_EXISTING", "board_id": matches[0]["id"], "name": source["name"]}, ensure_ascii=False))
            continue
        body = dict(source)
        server = next((s["server"] for s in existing if s["server"]["base_url"] == source.get("server", {}).get("base_url")), None)
        if server:
            body.pop("server")
            body["server_id"] = server["id"]
        created = request("/admin/sources", body)
        existing.append(created)
        print(json.dumps({"status": "CREATED", "board_id": created["id"], "name": created["name"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HTTPError as exc:
        print(f"관리자 API HTTP {exc.code}. 인증/권한/요청 형식을 확인하세요.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"등록 실패: {type(exc).__name__}. 설정과 서버 연결을 확인하세요.", file=sys.stderr)
        sys.exit(1)
