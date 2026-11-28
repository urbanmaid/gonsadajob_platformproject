# 공지 크롤러·AI 분석 (Python)

공지사항 개인화 플랫폼의 공지 수집·분석 파이프라인. 담당: 박기훈

- 죽전·천안 공식 학과·전공 117개 목록 / 공개 학과 게시판 161개 / 일반·대학 공통 게시판 5개
- 학과별 접근 점검과 Markdown·CSV 보고서 생성
- 단국대학교 공개 공지의 제목·본문·게시일·원문 주소·첨부파일 정보 수집
- `(board_id, source_key)` 중복 방지, 본문 변경 감지 및 재분석
- OpenAI API로 요약·분류·태그·참여 조건·신청 방법·준비물·일정 추출
- 관리자 API가 등록한 수집/재분석 `PENDING` 작업 처리
- DB: 로컬 SQLite, 운영 Supabase PostgreSQL. `server/`의 기존 공통 8개 테이블 사용

학과별 실행·설정은 [학과 공지 수집 안내](docs/departments.md), 접근 제한 학과는 [점검 보고서](reports/department_access_2026-11-29.md)를 먼저 확인한다.

## 처음 실행 (macOS)

저장소에서 `frontend/`, `server/`, `crawler/`를 나란히 둔다. Python 3.12 이상이 필요하며, 이번 오프라인 검증에는 Python 3.14.10을 사용했다.

```bash
cd gonsadajob_platformproject/crawler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env

python -m unittest discover -s tests -v
python scripts/demo_pipeline.py
python -m app.main preview --fixture
```

테스트와 데모는 네트워크·DB 계정·OpenAI 키 없이 실행할 수 있다. 데모 자료는 합성 공지이며 실제 AI 호출 결과가 아니다. PostgreSQL을 사용하지 않는다면 패키지 설치 전에도 위 세 명령을 실행할 수 있다.

### Git Bash / Windows

```bash
cd ~/projects/gonsa/crawler
py -3.14 -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m unittest discover -s tests -v
python scripts/demo_pipeline.py
```

## 기반 서버와 연결

1. `server/README.md`에 따라 서버를 실행하여 테이블을 만든다.
2. 크롤러 `.env`의 `DATABASE_URL`을 **서버와 같은 DB**로 맞춘다.
3. 관리자 API로 수집 대상 게시판을 등록한다.
4. 수집 결과를 미리 확인한 뒤 워커를 실행한다.

서버 기본 설정이 `sqlite:///./dev.db`라면 `crawler/.env`에는 `sqlite:///../server/dev.db`를 사용한다. 상대 경로는 각 명령을 실행하는 폴더 기준이다. 서버와 크롤러의 `app/` 패키지는 별도 프로세스에서 실행하며 서로 직접 import하지 않는다.

```bash
python -m app.main check
python scripts/check_server_contract.py
python scripts/register_sources.py
```

`check`는 공통 8개 테이블의 연결·컬럼을 읽어서 확인한다. `check_server_contract.py`는 `../server/app/models.py`의 컬럼 이름을 비교하는 정적 검사이며 자료형·권한·API 통합 검사를 대체하지 않는다. `register_sources.py`는 기본적으로 등록할 JSON만 출력한다.

### 수집 대상 등록

기본 등록 스크립트는 일반·공통 게시판 5개와 학과 게시판 161개를 합쳐 처리한다. 서버의 `/docs`에서 직접 등록한다면 `POST /api/v1/admin/sources`에 설정의 **객체 하나씩** 넣는다. 배열 전체를 요청 본문에 넣지 않는다.

스크립트를 사용할 경우 `.env`에 다음 두 항목을 추가한 뒤 실행한다. 토큰은 서버의 개발용 관리자 토큰 또는 실제 관리자 access token이다.

```dotenv
API_BASE_URL=http://127.0.0.1:8000/api/v1
ADMIN_ACCESS_TOKEN=
```

```bash
python scripts/register_sources.py --apply
```

기존에 같은 `list_url`이 있으면 건너뛰고, 같은 `base_url`의 서버가 있으면 `server_id`를 재사용한다. 기존 대상의 파서·활성 상태가 다르면 관리자가 `PATCH /admin/sources/{id}`로 수정한다. `crawler` DB 계정에는 수집 대상 INSERT 권한이 없으므로 이 등록 절차를 분리했다.

### 미리 보기와 실행

```bash
# 실제 웹 수집, 결과 출력만. DB 저장·AI 호출 없음
python -m app.main preview --limit 3

# 정기 작업 생성 → 수집 → 분석 대기 작업 처리
python -m app.main run-once

# 수집만 실행. API 키 없이 가능하며 분석은 PENDING으로 남음
python -m app.main run-once --crawl-only

# 대기 중인 분석만 실행. OPENAI_API_KEY 필요
python -m app.main run-once --analysis-only

# 관리자 요청만 처리 (정기 작업 생성 안 함)
python -m app.main run-once --no-schedule

# 기본 60초마다 큐 확인, 게시판의 수집 주기에 맞춰 작업 생성
python -m app.main run
```

`OPENAI_API_KEY`가 비어 있으면 AI를 호출하지 않고 분석 작업을 보존한다. 실제 분석은 OpenAI API를 사용하므로 해당 계정의 API 사용 요금이 발생한다. 키는 `crawler/.env`에만 넣는다.

## Supabase 연결

- 서버 담당자가 `server/sql/01_enable_rls.sql`, `02_crawler_role.sql`을 적용하고 `crawler` 전용 접속 주소를 전달한다.
- `.env`의 DB 주소를 `postgresql://...` 또는 서버와 같은 `postgresql+psycopg://...` 형식으로 설정한다.
- 워커 중복 실행을 막는 세션 잠금을 사용하므로 **Session pooler(5432) 또는 direct 연결**을 사용한다. Transaction pooler는 지원하지 않는다.
- 운영 주소에는 `sslmode=require`를 붙인다. 사용자 프로필·북마크·To-do 테이블에 대한 접근 권한은 필요하지 않다.
- 서버와 같은 DB를 사용하되 크롤러는 테이블을 새로 만들거나 기존 스키마를 변경하지 않는다.

## 처리 규약

| 항목 | 구현 |
|---|---|
| 공지 식별 | 게시판 ID + 원본 게시글 ID |
| 변경 판단 | 정규화한 제목·본문·첨부 메타데이터·본문 이미지 URL의 SHA-256 |
| 동일 내용 재수집 | 원문 주소·게시일 갱신, AI 작업 추가 없음 |
| 본문 변경 | 기존 현재 분석·대기 분석을 STALE로 처리하고 새 작업 생성 |
| 현재 분석 | 공지당 `is_current=true` 최대 1건, 조건·일정 저장과 같은 트랜잭션에서 교체 |
| 관리자 재분석 | 본문이 같으면 기존 현재 분석을 유지하다 새 결과가 성공할 때 교체 |
| 참여 조건 | 같은 `logic_group`은 AND, 그룹 간 OR. 학년은 숫자, 거주 형태는 DORM/OFF_CAMPUS/HOME |
| 불확실한 대상 | 필수 `other` 조건과 `REVIEW_REQUIRED`를 사용해 서버의 `NEEDS_CHECK` 판정 유도 |
| 날짜 | 근거와 시간대를 검증하고 UTC 저장. 날짜만 있는 마감은 한국 시간 당일 23:59:59 |
| 일정 갱신 | 유형·제목이 같은 일정의 ID 보존. 사라진 일정은 제거 |
| 첨부 | 파일 이름·URL·확장자 저장. 내용은 읽지 않으므로 `text_extracted=false`, `attachments_analyzed=false` |
| 수집 정책 | HTTPS 단국대 주소 및 공식 연결 외부 호스트 1개만 허용, robots.txt 확인, 기본 요청 간격 3초, GET 일시 오류 재시도 |
| 오류 복구 | 실패 이력 보존. AI POST는 중복 과금을 피하기 위해 자동 재시도하지 않음 |

수집 목록은 기본 최근 2페이지, 최대 40건이다. 매번 이 범위를 다시 확인해 기존 글의 수정도 감지한다. `checkpoint`는 관찰용 마지막 게시글 ID이며 이후 글만 수집하는 필터로 쓰지 않는다. 목록에 없다는 이유로 오래된 공지를 삭제하지 않는다.

본문이 바뀌면 기존 일정 날짜를 일단 비워 오래된 마감이 노출되지 않도록 한다. 분석 후 유형·제목이 같으면 ID를 재사용한다. 사용자가 이미 만들어 둔 To-do의 `due_at`은 이 파트가 변경하지 않는다. 해당 날짜 동기화는 서버 측 별도 기능이다.

## 다른 파트와 맞출 것

**기반 서버 (남예빈)**

- 공통 DB 8개 테이블의 이름·컬럼은 기존 서버 기준을 따른다.
- `crawl_logs.status=PENDING`, `notice_analysis.status=PENDING`을 워커가 소비한다.
- 개인별 자격 판정·추천은 기존 FastAPI가 수행한다. AI는 공지의 조건을 추출한다.
- 관리자 수집/재분석 요청 후 `GET /admin/crawl-jobs`, `GET /admin/analysis-jobs`로 상태를 확인한다.

**프론트엔드 (서지우)**

- 기존 서버의 `/api/v1/notices`, `/notices/{id}`, `/notices/{id}/eligibility`를 사용한다.
- `summary_lines`는 배열, `id`는 UUID, `source`는 객체라는 서버 형식을 따른다.
- `review_required`, `attachment_check_needed`, `NEEDS_CHECK` 상태를 표시한다.
- 프론트의 샘플 데이터 → 실제 API 교체 작업은 프론트 담당 영역이다.

## 폴더·파일 안내

| 경로 | 역할 |
|---|---|
| `app/main.py` | 실행 명령, 미리 보기, 반복 워커 |
| `app/config.py` | `.env` 및 실행 설정 |
| `app/database.py` | SQLite/PostgreSQL 연결, 트랜잭션, 중복 워커 잠금 |
| `app/models.py` | 수집 결과 자료형, 본문 해시 |
| `app/schemas.py` | AI 출력 JSON 스키마, 조건·일정 검증 |
| `app/http.py` | robots.txt, 요청 간격, GET 재시도 |
| `app/parsers/dankook.py` | 단국대 목록·상세 HTML 파싱 |
| `app/services/notices.py` | 공지·첨부 저장, 분석 교체, 일정 동기화 |
| `app/services/analysis.py` | OpenAI API 호출 및 응답 검사 |
| `app/services/pipeline.py` | 정기 작업·수동 작업·분석 큐 처리 |
| `app/prompts/notice_v1.txt` | AI 분석 지시문 |
| `config/sources.json` | 일반·대학 공통 게시판 5개 |
| `config/departments.json` | 공식 학과·전공 117개와 게시판 상태 |
| `config/department_sources.json` | 고유 공개 학과 게시판 161개 등록 설정 |
| `app/services/catalog.py` | 카탈로그·공유 URL 정리·접근 점검·보고서 |
| `scripts/check_departments.py` | 전체/학과별 접근 점검 CLI |
| `reports/` | 접근 제한 목록, 전체 목록, CSV·JSON |
| `scripts/register_sources.py` | 수집 대상 등록 보조 |
| `scripts/check_server_contract.py` | 서버 컬럼 이름 비교 |
| `scripts/demo_pipeline.py` | 실제 서비스와 분리된 메모리 DB 데모 |
| `tests/` | 파서·분석·저장·오류·작업 처리 회귀 테스트 |
| `docs/integration.md` | 연동 순서, 상태 확인, 오류 복구 |
| `docs/github_upload.md` | GitHub 업로드 순서, 커밋·PR 설명 예시 |
| `docs/verification.md` | 검증 결과와 남은 확인 사항 |

폴더는 소문자, Python 파일은 `snake_case`, 클래스는 `PascalCase`로 통일했다. 저장소 내 기존 `server/app`, `server/scripts`, `server/tests`, `server/README.md` 구성을 참고했다.

## 현재 지원 범위

- 기본 대상: [단국대 일반공지](https://www.dankook.ac.kr/web/kor/-390) + 공개 학과 게시판 161개 + 대학 공통 게시판 4개. `dku_bbs_web_BbsPortlet` 목록·블로그형과 상세를 지원한다.
- 공식 학과 117개를 모두 목록에 남기되 접근 제한·공지 미표시·링크 부재 항목은 수집 대상에서 제외하고 [별도 보고서](reports/department_access_2026-11-29.md)에 표시한다.
- 브라우저 확인과 실제 HTTP 수집 성공을 구분한다. 이 환경에서는 터미널 DNS 제한으로 자동 HTTP 수집을 끝까지 검증하지 못했다.
- PDF/HWP/HWPX 내용 추출, OCR, 이미지 분석, 로그인 필요 게시판, 삭제 공지 자동 비활성화는 포함하지 않는다.
- 첨부나 이미지가 있으면 이 버전은 보수적으로 검토 대상으로 둔다. 같은 URL의 첨부파일 바이트만 바뀐 경우는 다운로드하지 않으므로 감지하지 못한다.
- 최근 수집 범위를 벗어난 오래된 글 수정은 자동 감지하지 못한다. 초기 수집·점검 시 페이지 수를 늘려야 한다.
- 검증한 서버 기준 커밋: `5fa8cf51d59f30242ba1771a94cb91e67de90c0e`.

상세 검증 내역과 실제 서비스에서 확인할 항목은 [검증 기록](docs/verification.md)에 정리했다.
