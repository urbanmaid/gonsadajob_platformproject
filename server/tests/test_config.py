import pytest
from pydantic import ValidationError

from app.config import Settings

EXAMPLE = "change-me-to-a-random-string-of-32-chars-or-more"
REAL = "x" * 40
SUPABASE = "https://abcd.supabase.co"


def make(**kwargs) -> Settings:
    base = {"supabase_url": "", "environment": "development", "database_url": "sqlite:///./dev.db"}
    return Settings(_env_file=None, **{**base, **kwargs})


def test_example_secret_allowed_for_local_sqlite():
    assert make(jwt_secret=EXAMPLE).jwt_secret == EXAMPLE


@pytest.mark.parametrize(
    "backend",
    [
        {"supabase_url": SUPABASE},
        {"environment": "production"},
        {"database_url": "postgresql://postgres.abcd:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"},
    ],
)
def test_example_or_short_secret_rejected_for_real_backend(backend):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(jwt_secret=EXAMPLE, **backend)
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(jwt_secret="too-short", **backend)


def test_real_or_empty_secret_allowed_for_supabase():
    assert make(jwt_secret=REAL, supabase_url=SUPABASE).jwt_secret == REAL
    assert not make(jwt_secret="", supabase_url=SUPABASE).jwt_secret  # 새 서명 키(ES256)만 쓰는 경우
