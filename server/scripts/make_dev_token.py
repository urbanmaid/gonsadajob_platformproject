"""개발용 로그인 토큰 발급 (Supabase 연동 전 테스트용).

.env의 JWT_SECRET으로 Supabase와 같은 형식의 HS256 토큰을 만든다.
    python scripts/make_dev_token.py            # 일반 사용자
    python scripts/make_dev_token.py --admin    # 관리자
    python scripts/make_dev_token.py --user-id 2b0c...   # 특정 사용자 UUID로

출력된 토큰을 Swagger(/docs) 오른쪽 위 Authorize 버튼에 붙여 넣으면 된다.
운영 환경(ENVIRONMENT=production)에서는 실행되지 않는다.
"""

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt  # noqa: E402

from app.config import get_settings  # noqa: E402

# 고정 UUID를 쓰면 토큰을 다시 만들어도 같은 사용자로 유지된다
DEV_USER_ID = "00000000-0000-4000-8000-000000000001"
DEV_ADMIN_ID = "00000000-0000-4000-8000-0000000000ad"


def main() -> None:
    parser = argparse.ArgumentParser(description="개발용 JWT 발급")
    parser.add_argument("--admin", action="store_true", help="관리자 토큰")
    parser.add_argument("--user-id", help="사용자 UUID (생략 시 개발용 고정 UUID)")
    parser.add_argument("--email", default=None)
    parser.add_argument("--hours", type=int, default=24, help="유효 시간 (기본 24시간)")
    args = parser.parse_args()

    settings = get_settings()
    if settings.environment == "production":
        sys.exit("운영 환경에서는 개발용 토큰을 만들 수 없습니다.")
    if not settings.jwt_secret:
        sys.exit("server/.env에 JWT_SECRET을 먼저 설정하세요 (.env.example 참고).")

    user_id = str(uuid.UUID(args.user_id)) if args.user_id else (DEV_ADMIN_ID if args.admin else DEV_USER_ID)
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": settings.jwt_audience,
        "role": "authenticated",
        "email": args.email or ("admin@dev.local" if args.admin else "student@dev.local"),
        "iat": now,
        "exp": now + args.hours * 3600,
        "app_metadata": {"role": "admin"} if args.admin else {},
    }
    if settings.effective_jwt_issuer:
        payload["iss"] = settings.effective_jwt_issuer

    print(jwt.encode(payload, settings.jwt_secret, algorithm="HS256"))


if __name__ == "__main__":
    main()
