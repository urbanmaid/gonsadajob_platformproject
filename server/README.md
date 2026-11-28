# 기반 서버 (FastAPI)

공지사항 개인화 플랫폼의 백엔드. 담당: 남예빈

- 사용자 프로필·자격 정보, 공지 조회·검색, 참여 가능 여부 판정, 맞춤 추천
- 북마크, To-do, 활동 기록, 관리자(수집 대상·수집/재분석 작업) API
- 인증: Supabase Auth JWT 검증 (요청 본문의 user_id는 믿지 않음)
- DB: 로컬은 SQLite, 운영은 Supabase PostgreSQL (`DATABASE_URL`만 바꾸면 됨)

## 처음 실행 (Git Bash, Windows)

```bash
cd ~/projects/gonsa/server
py -3.14 -m venv .venv          # 이미 만들었으면 생략
source .venv/Scripts/activate   # 프롬프트 앞에 (.venv)가 보이면 성공
pip install -r requirements.txt
cp .env.example .env            # 필요하면 값 수정

pytest                          # 테스트 (전부 passed 나와야 정상)
python scripts/seed_dev_data.py # 샘플 공지 6건 넣기 (프론트 데모 데이터와 동일)
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs 에서 API 문서 확인
```

### 로그인이 필요한 API 테스트하기 (Supabase 연동 전)

```bash
python scripts/make_dev_token.py          # 학생 토큰
python scripts/make_dev_token.py --admin  # 관리자 토큰
```

출력된 토큰을 `/docs` 오른쪽 위 **Authorize** 버튼에 붙여 넣으면 된다.

## API 요약 (`/api/v1`)

| 구분 | 메서드·경로 | 설명 | 로그인 |
|---|---|---|---|
| 사용자 | `GET/PATCH/DELETE /users/me` | 내 프로필 조회·수정·탈퇴 | 필요 |
| | `GET/PUT /users/me/qualifications` | 자격 정보 조회·전체 교체 | 필요 |
| 공지 | `GET /notices` | 목록·검색 (`q`, `category`, `board_id`, `open_only`, `sort=latest\|deadline`) | 선택 |
| | `GET /notices/{id}` | 상세 (요약·조건·일정·첨부) | 선택 |
| 개인화 | `GET /notices/{id}/eligibility` | 참여 가능 여부 판정 | 필요 |
| | `GET /recommendations` | 맞춤 추천 | 필요 |
| 북마크 | `GET/POST /bookmarks`, `DELETE /bookmarks/{notice_id}` | | 필요 |
| To-do | `GET/POST /todos`, `PATCH/DELETE /todos/{id}` | 공지·일정에서 자동 생성 가능 | 필요 |
| 활동 | `POST /activities` | 검색어·열람 기록 | 필요 |
| 관리자 | `GET/POST /admin/sources`, `PATCH /admin/sources/{id}` | 수집 대상 게시판 | 관리자 |
| | `POST/GET /admin/crawl-jobs` | 수동 수집 요청·기록 | 관리자 |
| | `POST /admin/notices/{id}/reanalyze`, `GET /admin/analysis-jobs` | 재분석 요청·상태 | 관리자 |
| 시스템 | `GET /health` | 서버·DB 상태 | 불필요 |

공통 규약
- 오류: `{"error": {"code": "...", "message": "...", "details": []}}`
- 목록: `?page=1&limit=20` (최대 100) → `{"items", "page", "limit", "total"}`
- 시간: UTC로 저장·응답. 요청 시간에는 시간대를 붙인다 (`2026-12-10T18:00:00+09:00`)

## 다른 파트와 맞출 것

**크롤러·AI (박기훈)** — 공통 DB 테이블에 직접 쓰는 방식

- `notices`: `(board_id, source_key)`로 중복 판단, 본문이 바뀌면 `content_hash` 갱신
- `notice_analysis`: 공지당 `is_current=true`는 한 건만. 새 분석 확정 시 기존 건을 false로
- `notice_requirements`: 같은 `logic_group`은 AND, 다른 그룹끼리는 OR
  - `type`: department, year, campus, residence, gpa, language_score, certificate, benefit_status, volunteer_hours, other
  - `operator`: eq, ne, gte, lte, in(값은 쉼표 구분), contains
  - `language_score`는 `unit`에 시험명(TOEIC 등), `residence` 값은 DORM / OFF_CAMPUS / HOME
- `notice_events`: 마감은 `event_type=APPLICATION_DEADLINE`. 날짜가 불명확하면 비워 둠
- 관리자가 요청한 작업은 `crawl_logs.status=PENDING`, `notice_analysis.status=PENDING`으로 등록됨 → 가져가서 실행 후 상태 갱신

**프론트엔드 (서지우)**

- API 주소: `http://127.0.0.1:8000/api/v1`, 문서: `/docs`
- 로그인 후 Supabase access token을 `Authorization: Bearer <token>` 헤더로 전송
- 샘플 데이터(`seed_dev_data.py`)는 `noticeData.js`와 같은 6건

## 폴더 구조

```
server/
├─ app/
│  ├─ main.py            앱 생성, 라우터 등록, /health
│  ├─ config.py          .env 설정
│  ├─ database.py        DB 연결
│  ├─ models.py          테이블 정의 (노션 ERD)
│  ├─ schemas.py         요청·응답 형식
│  ├─ auth.py            JWT 검증, 관리자 권한
│  ├─ errors.py          공통 오류 형식
│  ├─ pagination.py      페이지네이션
│  ├─ services/          공지 조회, 참여 가능 여부 판정
│  └─ routers/           API 엔드포인트
├─ scripts/              개발용 토큰 발급, 샘플 데이터
└─ tests/                pytest
```
