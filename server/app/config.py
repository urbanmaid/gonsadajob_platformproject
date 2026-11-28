"""환경 설정.

값은 server/.env 파일(또는 환경 변수)에서 읽는다. 예시는 .env.example 참고.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env.example에 공개된 예시 값의 앞부분. 이 값으로는 실제 환경에서 서버가 뜨지 않게 막는다.
EXAMPLE_JWT_SECRET_PREFIX = "change-me"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Gonsadajob API"
    environment: str = "development"

    # DB: 기본은 로컬 SQLite. Supabase로 바꿀 때는
    # postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres 형식으로 교체한다.
    database_url: str = "sqlite:///./dev.db"
    # 개발용: 서버 시작 시 없는 테이블을 자동 생성한다. 운영에서는 마이그레이션 도구 사용 권장.
    auto_create_tables: bool = True

    # 프론트엔드 주소. 여러 개면 쉼표로 구분.
    cors_origins: str = "http://localhost:3000"

    # 인증 (Supabase Auth JWT)
    # - 비대칭 서명 키(RS256/ES256)를 쓰는 Supabase 프로젝트: SUPABASE_URL만 설정하면 JWKS로 검증
    # - 대칭 키(HS256, 레거시 JWT Secret) 또는 로컬 개발: JWT_SECRET 설정
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None  # 회원 탈퇴 시 인증 계정까지 삭제할 때만 필요
    jwt_secret: str | None = None
    jwt_audience: str = "authenticated"
    jwt_issuer: str | None = None

    # 관리자 사용자 UUID 목록(쉼표 구분). JWT app_metadata.role == "admin"인 사용자도 관리자로 본다.
    admin_user_ids: str = ""

    # 비회원도 공지 목록·상세를 볼 수 있는지
    notices_public: bool = True

    # 검색·열람 기록 보관 기간(일)
    activity_retention_days: int = 90

    @property
    def uses_real_backend(self) -> bool:
        """Supabase나 운영 환경에 연결된 상태인지 (로컬 SQLite 개발이 아닌지)."""
        return (
            bool(self.supabase_url)
            or self.environment == "production"
            or self.database_url.startswith(("postgres://", "postgresql"))
        )

    @model_validator(mode="after")
    def _reject_insecure_jwt_secret(self) -> "Settings":
        """예시 값이나 짧은 JWT_SECRET으로 실제 환경에 연결하면 서버 시작을 막는다.

        예시 값은 깃허브에 공개되어 있어, 그대로 쓰면 누구나 로그인 토큰을 위조할 수 있다.
        로컬 SQLite 개발 중에는 편의를 위해 허용한다.
        """
        secret = self.jwt_secret
        if not secret or not self.uses_real_backend:
            return self
        if secret.startswith(EXAMPLE_JWT_SECRET_PREFIX) or len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "JWT_SECRET이 예시 값이거나 너무 짧습니다. Supabase에 연결할 때는 "
                "Project Settings > JWT Keys의 Legacy JWT secret으로 바꾸거나, "
                "새 서명 키(ES256)만 쓰는 프로젝트라면 JWT_SECRET을 비워 두세요."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_user_id_set(self) -> set[str]:
        return {u.strip().lower() for u in self.admin_user_ids.split(",") if u.strip()}

    @property
    def effective_jwt_issuer(self) -> str | None:
        if self.jwt_issuer:
            return self.jwt_issuer
        if self.supabase_url:
            return self.supabase_url.rstrip("/") + "/auth/v1"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
