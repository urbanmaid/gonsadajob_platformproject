# 죽전·천안 학과별 공지 수집

## 범위와 확인 결과

2026-11-29 한국 시간 기준 단국대학교 공식 학부 대학 소개 24개 페이지의 학과·학부·전공 카드 **117개(죽전 58 / 천안 59)**를 목록화했다. 대학원 독립 학과, 연구실, 동아리, 폐지된 구 홈페이지를 모두 포함한다는 의미는 아니다. 학과 홈페이지에 함께 운영 중인 대학원 공지는 포함했다. 공식 목록에 홈페이지 링크가 없는 학과도 삭제하지 않았다.

- 학과 홈페이지 링크가 있는 항목 113개 / 공유 홈페이지를 합친 실제 홈페이지 104곳: 브라우저 접속 성공.
- 학과별로 설정한 고유 공개 게시판 161개: 156개는 공개 글 링크, 5개는 정상 빈 목록 확인.
- 일반공지 1개 + 퇴계혁신칼리지·율곡혁신칼리지·자유교양대학·프리무스국제대학 공통 공지 4개 추가.
- 기본 등록 대상은 총 **166개 게시판**. robots 정책이나 개별 상세 글 권한 때문에 실제 HTTP 수집 시 제한될 수 있다.
- CMS, 법과대학, 의과대학, 프리무스국제대학, 물리학과 블로그형 목록의 공지 상세 5개를 표본 확인했다. 모든 과거 게시글과 첨부 내용을 열람한 것은 아니다.

| 학과·전공 단위 결과 | 수 |
|---|---:|
| 설정한 공지 게시판 모두 공개 | 68 |
| 일부 게시판만 공개 | 13 |
| 로그인 필요 | 1 |
| 공지 게시판 접근 거부 | 12 |
| 공지 메뉴는 있으나 본문 미표시 | 16 |
| 공지 링크 미확인 | 3 |
| 공식 학과 홈페이지 링크 없음 | 4 |

정상 빈 게시판도 수집 가능에 포함한다. 예를 들어 체육교육과는 학생회 공지는 정상 빈 목록이고 학과 공지는 본문 미표시이므로 `PARTIAL`이다. 해당 학과의 최신 공지가 확보되었다는 뜻은 아니다.

[학과별 제한 목록과 전체 목록](../reports/department_access_2026-11-29.md), [CSV](../reports/department_access_2026-11-29.csv), [공통 교육단위 결과](../reports/shared_college_access_2026-11-29.md)에 주소까지 정리했다.

공식 홈페이지 링크가 없는 학과는 바이오소재융합공학과, 한국학과, 연기영상예술학과, 국제스포츠학부 골프전공이다. 앞의 3개는 프리무스국제대학 공통 공지를 별도 소스로 제공한다. 이를 학과 자체 홈페이지가 확인된 것으로 표시하지 않는다.

## 설정 파일

| 파일 | 내용 |
|---|---|
| `config/colleges.json` | 공식 대학 안내 24개 페이지, 기준 학과 수 |
| `config/departments.json` | 117개 학과·전공, 출처, 홈페이지, 게시판별 확인 상태 |
| `config/department_sources.json` | 161개 공개 게시판의 서버 관리자 API 요청 객체 |
| `config/sources.json` | 기존 일반공지 + 추가 대학 공통 공지 4개 |
| `config/shared_colleges.json` | 공통 교육단위 재점검용 목록 |
| `reports/browser_survey.json` | 고유 학과 홈페이지 104곳의 확인 결과 |

학과를 합쳐 없애지 않는다. 공유 게시판을 한 번 등록·수집하면서 모든 관련 학과 항목이 같은 `list_url`을 참조한다. 법과대학·의과대학에서 관측한 `/web/.../-번호`와 `/-번호` 별칭도 정규화한다. 서로 다른 게시판에 같은 내용이 다시 게시된 경우는 각 출처를 유지한다.

## 점검과 등록

모든 명령은 `crawler/` 안에서 실행한다. 접근 점검에는 DB와 OpenAI 키가 필요하지 않다.

```bash
# 포함된 브라우저 점검 자료로 보고서만 생성
python scripts/check_departments.py --offline

# 현재 상태를 HTTP로 재점검: JSON / CSV / Markdown 생성
python scripts/check_departments.py

# 특정 캠퍼스 또는 학과만 점검
python scripts/check_departments.py --campus 죽전
python scripts/check_departments.py --department 컴퓨터공학과

# 대학 공통 공지 4개 점검
python scripts/check_departments.py --catalog config/shared_colleges.json --output reports/shared_college_access_latest

# 현재 수집 가능한 게시판 설정을 별도 파일로 출력
python scripts/check_departments.py --sources-output reports/department_sources_latest.json

# 일반 + 학과 + 대학 공통 166개 등록 계획 출력 (서버 변경 없음)
python scripts/register_sources.py

# .env의 관리자 토큰으로 실제 등록
python scripts/register_sources.py --apply

# 특정 학과만 등록
python scripts/register_sources.py --department 컴퓨터공학과 --apply

# 재점검으로 생성한 공개 게시판 목록 등록
python scripts/register_sources.py --config reports/department_sources_latest.json --apply
```

점검 스크립트는 학과 홈페이지에서 공지·장학·취업 링크 후보를 추가 발견하고 공개 목록을 검증한다. 저장된 비공개·미표시 게시판도 다시 확인하므로 사이트가 복구되면 새 설정으로 출력할 수 있다. 현재 카탈로그에 없는 신설 학과는 공식 안내와 대조하여 `departments.json`에 추가해야 한다. 점검 결과가 기본 카탈로그나 서버의 기존 활성 상태를 자동으로 덮어쓰지는 않는다.

등록 스크립트는 같은 URL을 재등록하지 않고 기존 서버 객체를 재사용한다. 기존 등록의 주소·활성 상태 변경은 관리자 API `PATCH /admin/sources/{id}`로 반영한다. 실패한 게시판의 이유는 보고서와 `crawl_logs.error_message`에서 확인한다.

## 실행

```bash
# 실제 원문 1건 확인: DB/AI 호출 없음
python -m app.main preview --url https://cms.dankook.ac.kr/web/ace/notice --limit 1

# 전체 등록 게시판을 계속 수집
python -m app.main run --crawl-only

# 한 번 실행하며 최대 200개 대기 작업 처리
python -m app.main run-once --crawl-only --max-jobs 200

# 캠퍼스 / 학과별로 수집 큐 선택
python -m app.main run-once --crawl-only --campus 천안 --max-jobs 200
python -m app.main run-once --crawl-only --department 컴퓨터공학과

# AI는 전체 공통 분석 큐를 별도로 처리
python -m app.main run --analysis-only
```

`--campus`/`--department`는 기본 학과 카탈로그를 기준으로 **수집 큐만** 선택한다. 일반·대학 공통 공지는 선택하지 않으므로 전체 실행에서 수집한다. 이 옵션에는 `--crawl-only`를 함께 사용한다. 선택 밖의 대기 작업을 실패 처리하거나 소비하지 않는다. 워커는 동일 DB에서 동시에 하나만 실행할 수 있다.

한 번 실행의 기본 처리량은 게시판 10개다. `--max-jobs 200` 또는 반복 `run`을 사용해야 전체 대기 작업이 처리된다. 게시판별 기본 수집 범위는 최근 2페이지, 최대 40개이며 과거 글 전체 다운로드는 아니다. 최초 소규모 확인은 `.env`에서 `PAGES_PER_BOARD=1`, `NOTICES_PER_BOARD=5`로 줄일 수 있다.

학과 게시판은 기본 180분 주기이며 요청은 같은 호스트당 최소 3초 간격으로 순차 처리한다. 161개 게시판의 최초 수집은 오래 걸릴 수 있다. 공유 홈페이지를 병렬로 과도하게 요청하지 않는다. 이미 저장된 글도 설정한 최근 범위에서 수정 여부를 확인하되 본문 해시가 같으면 새 AI 작업을 만들지 않는다.

## 오류와 처리 원칙

- `LOGIN_REQUIRED` / `ACCESS_DENIED`: 공개 열람 제한, 우회 수집하지 않음.
- `NO_PUBLIC_ITEMS`: 목록은 있지만 공개 글 없음. 정상 빈 목록과 구분.
- `BOARD_NOT_DISPLAYED`: 메뉴·제목만 있거나 지원 목록 구조 없음. 학과가 폐지됐다고 단정하지 않음.
- `ROBOTS_DENIED` / `ROBOTS_UNAVAILABLE` / `ROBOTS_INVALID` / `ROBOTS_REDIRECT`: 해당 환경의 수집 정책 확인 필요.
- `NETWORK_ERROR` / `HTTP_ERROR`: 실행 환경 또는 원격 응답 오류. 다른 학과 점검은 계속함.
- 주소 이동: 목적지의 HTTPS·허용 호스트·robots 규칙을 다시 확인한 후 이동. 로그인 화면과 순환 이동은 중단.
- 외부 예외 호스트는 공식 안내가 연결한 `ai-architecture-website.pages.dev` 하나뿐이다. 현재 공지 링크가 없어 활성 게시판으로 등록하지 않는다.

학과별 출처 메타데이터는 카탈로그에 보존한다. 기존 서버 DB에는 별도 학과 매핑 테이블을 만들지 않았으므로 프론트의 사용자 학과 필터·관련 학과 추천까지 새로 구현한 것은 아니다. 공지의 실제 신청 대상은 원문의 근거를 통해 분석한다.
