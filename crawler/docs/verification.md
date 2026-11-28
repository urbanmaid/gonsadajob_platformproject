# 구현 및 검증 기록

확인일: 2026-11-29 (한국 시간)

## 기준

- 저장소: https://github.com/urbanmaid/gonsadajob_platformproject
- 서버·프론트 검토 기준 커밋: `5fa8cf51d59f30242ba1771a94cb91e67de90c0e`
- 기존 서버 테이블·상태값·관리자 작업 등록 규약을 기준으로 구현했다.
- 일반공지 목록과 게시글 상세의 실제 DOM에서 `dku-list-body-item`, `viewMessage`, `bbsMessageId`, `dku-bbs-view_message-inner`, `r_cont`, 첨부 링크 구조를 확인했다.
- OpenAI 구조화 출력 공식 문서의 Responses API `text.format`, `json_schema`, `strict`, 완료·거절 처리 형식을 참고했다.

## 수행한 검증

| 검증 | 결과·범위 |
|---|---|
| Python 컴파일 | 구현 모듈 문법 확인 |
| `python -m unittest discover -s tests -v` | 54개 통과. 파서·해시·AI 응답 검증·작업 큐·SQLite 저장·실패 복구 |
| `python scripts/demo_pipeline.py` | 합성 HTML → 메모리 DB 저장 → 모의 분석 → 현재 분석 1건 → 동일 공지 재수집 변화 없음 |
| `python -m app.main preview --fixture` | 네트워크 없이 파서 결과·첨부 URL·해시 출력 |
| `python scripts/check_server_contract.py` | 기준 서버의 공통 8개 테이블 컬럼 이름 일치 |
| 공개 웹 페이지 확인 | 학과·전공 117개, 고유 홈페이지 104곳, 학과 공개 게시판 161개, 대학 공통 공지 4개. 상세 5개 표본 확인. 자동 HTTP 수집 검증과 구분 |
| 확장 회귀 테스트 | 공유 학과·주소 중복 제거, 선택 큐 격리, 빈 목록/접근 거부 구분, 블로그형 파서, 리다이렉트 목적지 robots 검사, 오류 후 다음 학과 계속 점검 |

테스트 자료는 실제 공지 형식을 참고해 작성한 합성 HTML·JSON이다. 모의 분석 모델 이름은 `fixture-only-not-a-real-model`이며, 데모 실행 시 `real_api_called=false`를 출력한다.

## 실제 연결 후 확인할 사항

- 이 작업 환경의 터미널 네트워크에서 DNS 요청이 제한되어 실제 크롤러의 학교 HTTP 수집을 끝까지 실행하지 못했다. 브라우저에서 확인한 DOM을 토대로 파서를 구현했다. 팀 환경에서 `preview --limit 1`로 robots 정책과 서버 응답을 함께 확인한다.
- OpenAI 키를 제공받지 않아 실제 모델 호출·요약 품질·토큰 비용을 검증하지 않았다. 요청/응답 처리는 모의 응답으로 테스트했다.
- Supabase 접속 정보가 없어 PostgreSQL 드라이버, 실제 RLS 권한, 세션 잠금을 운영 DB에서 실행하지 않았다. SQLite 검증과 동일하다고 주장하지 않는다.
- 서버 의존 패키지를 실행 환경에 설치할 수 없어 서버를 띄운 HTTP API 통합 테스트는 수행하지 않았다. 컬럼 이름 정적 검사와 서버 모델에 대응한 SQLite 테스트 스키마를 사용했다.
- 프론트 화면은 변경하지 않았다. 실제 API 데이터 표시와 사용자별 참여 판정은 팀 통합 단계에서 확인한다.

## 운영 전 최소 확인 순서

1. `check` 성공, 실제 게시판 `preview` 성공.
2. 관리자 수집 요청 → `SUCCEEDED` 또는 원인을 설명하는 실패 코드.
3. 같은 게시글을 재수집했을 때 공지 수가 늘지 않음.
4. 실제 분석 1건 실행 → 서버 공지 상세에 요약·조건·일정·첨부 상태 표시.
5. 같은 본문의 재분석 실패 시 기존 결과 유지.
6. 별도 워커 실행 시 중복 실행 차단.
7. 테스트용 게시글/자료로 본문 변경 시 STALE → 새 분석 확정 과정 확인.

## 참고 링크

- [기반 서버 README](https://github.com/urbanmaid/gonsadajob_platformproject/tree/main/server)
- [단국대학교 일반공지](https://www.dankook.ac.kr/web/kor/-390)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
