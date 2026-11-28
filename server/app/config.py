"""환경 설정.

값은 server/.env 파일(또는 환경 변수)에서 읽는다. 예시는 .env.example 참고.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
