from app.database import normalize_database_url


def test_supabase_url_gets_psycopg_driver():
    raw = "postgresql://postgres.abc:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
    assert normalize_database_url(raw).startswith("postgresql+psycopg://postgres.abc:pw@")
    assert normalize_database_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_other_urls_unchanged():
    for url in ("sqlite:///./dev.db", "sqlite://", "postgresql+psycopg://u:p@h/db"):
        assert normalize_database_url(url) == url
