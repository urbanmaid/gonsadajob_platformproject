-- 테스트 전용 SQLite 스키마. 운영 DB 생성/마이그레이션에 사용하지 않는다.
-- server/app/models.py @ 5fa8cf51d59f30242ba1771a94cb91e67de90c0e 기준.
CREATE TABLE source_servers (
 id CHAR(32) PRIMARY KEY NOT NULL, name VARCHAR(100) NOT NULL, base_url VARCHAR(500) NOT NULL,
 interface VARCHAR(20) NOT NULL, location VARCHAR(100), rate_limit_per_minute INTEGER,
 crawl_allowed BOOLEAN NOT NULL, access_restricted BOOLEAN NOT NULL,
 created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE source_boards (
 id CHAR(32) PRIMARY KEY NOT NULL, server_id CHAR(32) NOT NULL REFERENCES source_servers(id) ON DELETE CASCADE,
 name VARCHAR(100) NOT NULL, list_url VARCHAR(1000) NOT NULL, category_hint VARCHAR(50),
 crawl_interval_minutes INTEGER NOT NULL, parser_version VARCHAR(50), is_active BOOLEAN NOT NULL,
 last_success_at DATETIME, checkpoint VARCHAR(200), created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE crawl_logs (
 id CHAR(32) PRIMARY KEY NOT NULL, board_id CHAR(32) REFERENCES source_boards(id) ON DELETE SET NULL,
 "trigger" VARCHAR(20) NOT NULL, status VARCHAR(20) NOT NULL, requested_by CHAR(32),
 started_at DATETIME, finished_at DATETIME, http_status INTEGER,
 fetched_count INTEGER NOT NULL, created_count INTEGER NOT NULL, updated_count INTEGER NOT NULL,
 error_message TEXT, created_at DATETIME NOT NULL
);
CREATE TABLE notices (
 id CHAR(32) PRIMARY KEY NOT NULL, board_id CHAR(32) NOT NULL REFERENCES source_boards(id) ON DELETE CASCADE,
 source_key VARCHAR(200) NOT NULL, title VARCHAR(500) NOT NULL, content_html TEXT, content_text TEXT,
 source_url VARCHAR(1000) NOT NULL, published_at DATETIME, content_hash VARCHAR(64) NOT NULL,
 status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
 UNIQUE(board_id, source_key)
);
CREATE TABLE notice_analysis (
 id CHAR(32) PRIMARY KEY NOT NULL, notice_id CHAR(32) NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
 content_hash VARCHAR(64) NOT NULL, status VARCHAR(20) NOT NULL, is_current BOOLEAN NOT NULL,
 summary_lines JSON, category VARCHAR(50), tags JSON, application_method TEXT, documents JSON,
 review_required BOOLEAN NOT NULL, attachments_analyzed BOOLEAN NOT NULL,
 model_version VARCHAR(100), prompt_version VARCHAR(50), schema_version VARCHAR(50), error_message TEXT,
 created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE notice_requirements (
 id CHAR(32) PRIMARY KEY NOT NULL, analysis_id CHAR(32) NOT NULL REFERENCES notice_analysis(id) ON DELETE CASCADE,
 logic_group INTEGER NOT NULL, type VARCHAR(30) NOT NULL, operator VARCHAR(10) NOT NULL,
 value VARCHAR(200), unit VARCHAR(20), mandatory BOOLEAN NOT NULL, evidence_text TEXT, confidence FLOAT
);
CREATE TABLE notice_events (
 id CHAR(32) PRIMARY KEY NOT NULL, notice_id CHAR(32) NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
 analysis_id CHAR(32) REFERENCES notice_analysis(id) ON DELETE SET NULL,
 event_type VARCHAR(30) NOT NULL, title VARCHAR(200) NOT NULL, start_at DATETIME, end_at DATETIME,
 precision VARCHAR(10) NOT NULL, timezone VARCHAR(40) NOT NULL
);
CREATE TABLE notice_attachments (
 id CHAR(32) PRIMARY KEY NOT NULL, notice_id CHAR(32) NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
 file_name VARCHAR(300) NOT NULL, file_url VARCHAR(1000) NOT NULL, file_type VARCHAR(20),
 size_bytes INTEGER, text_extracted BOOLEAN NOT NULL
);
