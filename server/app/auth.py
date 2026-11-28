"""Supabase Auth JWT 검증.

- 프론트엔드는 Supabase 로그인 후 받은 access token을 `Authorization: Bearer <token>`으로 보낸다.
- 서버는 서명·만료·발급자·대상(aud)을 검증하고, 토큰의 sub(사용자 UUID)만 권한 판단에 쓴다.
  요청 본문의 user_id는 절대 믿지 않는다 (노션 'API 공통 규약').
"""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)

_jwks_client: jwt.PyJWKClient | None = None


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str | None
    is_admin: bool


def _unauthorized(message: str = "로그인이 필요합니다.", code: str = "UNAUTHORIZED") -> AppError:
    return AppError(401, code, message)


def _get_jwks_client(settings: Settings) -> jwt.PyJWKClient:
    global _jwks_client
    if not settings.supabase_url:
        raise AppError(503, "AUTH_NOT_CONFIGURED", "서버 인증 설정(SUPABASE_URL)이 없습니다.")
    if _jwks_client is None:
        url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True)
    return _jwks_client


def decode_token(token: str, settings: Settings) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise _unauthorized("토큰 형식이 올바르지 않습니다.", "INVALID_TOKEN")

    alg = header.get("alg")
    kwargs: dict = {"audience": settings.jwt_audience, "options": {"require": ["exp", "sub"]}}
    issuer = settings.effective_jwt_issuer
    if issuer:
        kwargs["issuer"] = issuer

    try:
        if alg == "HS256":
            if not settings.jwt_secret:
                raise AppError(503, "AUTH_NOT_CONFIGURED", "서버 인증 설정(JWT_SECRET)이 없습니다.")
            return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], **kwargs)
        if alg in ("RS256", "ES256"):
            signing_key = _get_jwks_client(settings).get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=[alg], **kwargs)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("로그인이 만료되었습니다. 다시 로그인해 주세요.", "TOKEN_EXPIRED")
    except jwt.PyJWKClientConnectionError:
        raise AppError(503, "AUTH_UNAVAILABLE", "인증 서버에 연결할 수 없습니다.")
    except jwt.PyJWTError:
        raise _unauthorized("유효하지 않은 토큰입니다.", "INVALID_TOKEN")

    raise _unauthorized("지원하지 않는 토큰 서명 방식입니다.", "INVALID_TOKEN")


def _to_user(payload: dict, settings: Settings) -> CurrentUser:
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        raise _unauthorized("토큰의 사용자 정보가 올바르지 않습니다.", "INVALID_TOKEN")

    app_metadata = payload.get("app_metadata") or {}
    is_admin = app_metadata.get("role") == "admin" or str(user_id) in settings.admin_user_id_set
    return CurrentUser(id=user_id, email=payload.get("email"), is_admin=is_admin)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if credentials is None:
        raise _unauthorized()
    return _to_user(decode_token(credentials.credentials, settings), settings)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser | None:
    """토큰이 없으면 None, 있으면 검증한다 (잘못된 토큰은 401)."""
    if credentials is None:
        return None
    return _to_user(decode_token(credentials.credentials, settings), settings)


def get_notice_reader(
    user: CurrentUser | None = Depends(get_optional_user),
    settings: Settings = Depends(get_settings),
) -> CurrentUser | None:
    """공지 조회용. NOTICES_PUBLIC=false이면 로그인을 요구한다."""
    if user is None and not settings.notices_public:
        raise _unauthorized()
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise AppError(403, "FORBIDDEN", "관리자 권한이 필요합니다.")
    return user
