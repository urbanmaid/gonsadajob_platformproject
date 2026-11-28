# 서버·프론트 연동 안내

## 담당 범위

박기훈 파트는 공개 공지 수집 → 본문 정규화 → 공통 DB 저장 → AI 요약·조건·일정 추출까지 처리한다. 서버의 로그인·개인별 판정·북마크·To-do API와 프론트 화면은 기존 담당 파트를 사용한다.

## 연결 순서

1. 서버 담당자가 서버를 실행하고 DB 테이블을 준비한다.
2. 크롤러 `.env`에 동일 DB 주소를 설정한다. Supabase에서는 전용 `crawler` 계정을 사용한다.
3. `python -m app.main check`로 공통 8개 테이블이 보이는지 확인한다.
4. 서버 `/docs`에서 관리자 인증 후 `POST /api/v1/admin/sources`로 `config/sources.json`의 게시판 객체를 등록한다.
5. `python -m app.main preview --limit 1`로 실제 페이지 파싱 결과를 확인한다.
6. `python -m app.main run-once --crawl-only`로 원문을 저장한다.
7. `OPENAI_API_KEY`를 로컬 `.env`에 넣고 `python -m app.main run-once --analysis-only`로 분석한다.
8. 서버 `GET /api/v1/notices`와 공지 상세 API에서 제목·요약·조건·일정·첨부 정보를 확인한다.
9. 사용자 토큰으로 참여 가능 여부 API를 확인하고 프론트에 연결한다.

토큰·DB 비밀번호·API 키를 설명 문서나 스크린샷에 포함하지 않는다.

## 공통 DB 연결표

| 테이블 | 크롤러 동작 | 서버 동작 |
|---|---|---|
| `source_servers` | 읽기 | 관리자 등록 |
| `source_boards` | 읽기, 성공 시각·체크포인트 갱신 | 관리자 등록·수정 |
| `crawl_logs` | 스케줄 등록, PENDING 소비, 실행 결과 기록 | 수동 작업 등록·조회 |
| `notices` | 신규 저장·본문 변경 감지 | 공지 목록·상세 조회 |
| `notice_analysis` | 분석 작업 소비, 현재 분석 교체 | 결과 조회·재분석 요청 |
| `notice_requirements` | 조건 및 원문 근거 저장 | 사용자 정보와 규칙 비교 |
| `notice_events` | 일정 저장·갱신 | 마감 정렬·일정 조회·To-do 연결 |
| `notice_attachments` | 첨부 메타데이터 동기화 | 첨부 확인 안내 |

프론트에 크롤러 DB 계정이나 OpenAI 키를 전달하지 않는다. 프론트는 기반 서버 API만 호출한다.

## 관리자 요청 예시

아래 JSON은 서버 `/docs`의 해당 API 요청 본문으로 사용한다. 경로의 UUID는 등록 결과의 실제 값으로 교체한다.

### 수동 수집

`POST /api/v1/admin/crawl-jobs`

```json
{"board_id": "등록된-게시판-UUID"}
```

활성 게시판 전체 요청은 `{}`를 보낸다. 워커에서 `python -m app.main run-once --no-schedule --crawl-only`를 실행한다.

`GET /api/v1/admin/crawl-jobs`에서 `SUCCEEDED` 또는 실패 사유 코드를 확인한다.

### 재분석

`POST /api/v1/admin/notices/{notice_id}/reanalyze`

본문 없이 요청한다. 이후 `python -m app.main run-once --analysis-only`를 실행한다. 같은 본문에 대한 재분석이 실패해도 이전 현재 분석은 유지된다. 본문이 바뀐 경우에는 이전 결과가 STALE이므로 새 분석이 끝날 때까지 분석 결과가 없는 상태로 제공된다.

## 상태와 오류 복구

| 상태·코드 | 뜻 | 조치 |
|---|---|---|
| `PENDING` | 대기 중 | 워커 실행 여부 확인 |
| `RUNNING` | 처리 중 | 종료 전까지 기다림 |
| `SUCCEEDED` | 수집/분석 완료 | 서버 API로 결과 확인 |
| `PARTIAL` | 일부 공지만 수집 성공 | 실패 코드 확인 후 수집 재요청 |
| `REVIEW_REQUIRED` | 본문은 분석했으나 사람 확인 필요 | 원문·첨부 확인 |
| `STALE` | 원문 버전 변경 또는 더 이상 유효하지 않은 작업 | 최신 버전 분석 상태 확인 |
| `PARSER_STRUCTURE_CHANGED` | 목록·본문 구조 불일치 | `app/parsers/dankook.py`와 실제 HTML 비교 |
| `SOURCE_HTTP_403/429` | 접근 제한·요청 과다 | 정책·간격 확인. 우회하지 않음 |
| `SOURCE_POLICY_OR_DATA_INVALID` | robots 제한, 주소 이동, 비활성 설정 등 | 주소·수집 정책·파서 버전 확인 |
| `OPENAI_HTTP_401/403` | 키·API 권한 문제 | 로컬 키 설정 확인 |
| `OPENAI_HTTP_429` | API 한도·사용량 제한 | 사용량·한도 확인 후 관리자 재분석 요청 |
| `ANALYSIS_VALIDATION_FAILED` | 조건 근거·날짜·자료형 검증 실패 | 원문과 프롬프트 점검 후 재분석 |
| `NOTICE_TOO_LONG` | 본문 40,000자 초과 | 긴 본문 분할 분석 기능을 추가한 뒤 재분석 |

워커가 강제 종료되면 작업이 `RUNNING`에 남을 수 있다. 다른 워커가 종료된 것을 확인한 뒤 실행한다.

```bash
python -m app.main recover
```

이 명령은 DB의 워커 잠금을 확보한 뒤 중단 작업을 `FAILED / WORKER_INTERRUPTED`로 마감한다. 실행 중인 워커의 작업을 빼앗지 않는다. 실제 OpenAI 요청이 이미 전달됐을 수 있으므로 자동 재전송하지 않는다. 필요한 작업만 관리자 API에서 다시 요청한다.

## 게시판 추가·변경

1. 공개 URL, robots 정책, 목록·상세 페이지 구조를 직접 확인한다.
2. 현재 단국대 `dku_bbs_web_BbsPortlet` 구조라면 `config/sources.json`에 등록 객체를 추가한다.
3. `parser_version`은 `dku_bbs_v1`을 사용한다. 구조가 다르면 새 파서와 테스트를 먼저 추가한다.
4. 등록 스크립트 또는 관리자 API로 등록한다. 기존 항목 수정은 PATCH API를 사용한다.
5. `preview --url "실제-게시판-HTTPS-URL" --limit 1`과 수동 수집으로 확인한다.

교차 학과 공지는 원문이 명시한 조건을 그대로 저장한다. ‘소프트웨어학과 또는 컴퓨터공학과’는 `department / in / 소프트웨어학과,컴퓨터공학과`로 표현할 수 있다. 관련 학과를 프로필에 여러 개 저장하는 기능은 현재 서버 스키마에 없으므로 이 크롤러가 임의로 추가하지 않는다.
