# GitHub 업로드 안내

## 업로드할 위치

대상 저장소: https://github.com/urbanmaid/gonsadajob_platformproject

압축을 풀면 나온 `crawler/` 폴더를 저장소 최상위에 올린다. 기존 `frontend/`, `server/`와 같은 깊이다. `server/crawler/`나 `frontend/crawler/`에 넣지 않는다. ZIP 파일 자체를 코드 대신 올리지 않는다.

| 기존 파트 | 추가할 파트 |
|---|---|
| `frontend/` — 화면 | `crawler/` — 공지 수집·AI 분석 |
| `server/` — 기반 서버 | `crawler/app/`, `crawler/scripts/`, `crawler/tests/` |
| 파트별 `README.md` | `crawler/README.md` |

기존 서버·프론트 코드를 복사해서 다시 올릴 필요가 없다. 이번 업로드 파일은 모두 `crawler/` 아래에 모았다.

## GitHub 웹에서 업로드

1. 저장소 **Code** 화면에서 팀이 작업하는 브랜치를 선택한다.
2. 저장소 최상위에서 **Add file → Upload files**를 선택한다.
3. 압축을 푼 `crawler` 폴더를 끌어다 놓는다.
4. 파일 목록에 `crawler/app/main.py`, `crawler/README.md`처럼 경로가 표시되는지 확인한다.
5. 아래 커밋 제목·설명을 입력하고 팀에서 쓰는 브랜치 방식으로 커밋한다.
6. 업로드 후 `crawler/README.md`가 열리는지, `app`, `config`, `scripts`, `tests`, `docs` 폴더가 있는지 확인한다.

macOS 파일 창에서는 `.env.example`, `.gitignore`가 숨겨질 수 있다. `Command + Shift + .`로 숨김 파일을 표시하고 두 파일도 포함했는지 확인한다. 웹 업로드에서 빠졌다면 해당 경로로 파일을 생성해 내용을 넣거나 아래 Git 방식을 사용한다. 실제 `.env`, `.venv`, DB 파일은 업로드하지 않는다.

웹의 **Commit changes** 화면에서 새 브랜치를 만들면 이후 Pull Request 화면으로 진행할 수 있다. 팀원이 `main`에 직접 올리는 방식으로 합의했다면 같은 브랜치를 사용할 수 있다. 이번 패키지는 저장소에 아직 업로드하지 않은 로컬 구현물이다.

## Git 명령으로 업로드

기존 로컬 저장소에서 팀 작업 브랜치로 이동하고 최신 내용을 받은 다음 `crawler/`를 복사한다. 아래 예시는 별도 작업 브랜치를 만드는 방식이다.

```bash
git switch main
git pull --ff-only
git switch -c feature/crawler-ai
# 이 위치에 압축 해제한 crawler/ 폴더를 복사
git add crawler
git diff --cached --stat
git status --short
git commit -m "Implement Gonsadajob department notice crawler"
git push -u origin feature/crawler-ai
```

이미 같은 작업 브랜치가 있다면 `git switch feature/crawler-ai`로 이동한다. 커밋 전 `.env`, API 키, DB 파일이 목록에 없는지 확인한다. `git push` 뒤 GitHub에서 Pull Request를 만든다.

## 커밋 제목 예시

기존 프론트 커밋 `Implement Gonsadajob frontend MVP`와 비슷한 형식이다.

```text
Implement Gonsadajob department notice crawler
```

## 커밋 설명 / Pull Request 본문 예시

```text
단국대 공지 수집과 AI 분석을 담당하는 crawler/ 파트를 추가했습니다.

- 1차 일반공지·AI 파이프라인 유지
- 죽전/천안 공식 학과·전공 117개와 홈페이지 104곳 확인
- 공개 학과 게시판 161개 + 일반/대학 공통 5개 등록 설정
- 캠퍼스/학과 선택 실행, 공유 게시판 중복 방지
- 접근 거부/로그인 필요/공지 미표시/홈페이지 링크 부재 보고서
- 일반공지와 학과 공지의 제목·본문·게시일·원문 주소·첨부파일 정보 수집
- 게시판/원본 ID 기반 중복 방지와 본문 해시 기반 변경 감지
- OpenAI 구조화 출력으로 요약·분류·참여 조건·준비물·일정 추출
- 서버 공통 8개 테이블 연동 및 관리자 수집/재분석 대기 작업 처리
- 공지당 현재 분석 1건 유지, 근거가 부족한 조건은 검토 필요 처리
- 파트별 README, 실행·연동·업로드 안내와 오프라인 테스트 추가

검증: Python 3.14.10에서 unittest 54개 통과, 오프라인 파이프라인 데모,
서버 공통 8개 테이블 컬럼 이름 비교를 수행했습니다.

실제 OpenAI 키와 Supabase 계정 연결 검증은 팀 환경에서 진행해야 합니다.
브라우저 열람과 오프라인 테스트를 수행했으며 자동 HTTP 수집은 실행 환경의 DNS 제한으로 미검증입니다. PDF/HWP/OCR 본문 분석은 포함하지 않습니다.
```

## 팀원에게 설명할 문장

> 제가 맡은 공지 크롤러·AI 분석 코드를 `crawler/`에 추가했습니다. 서버와 비슷하게 `app`, `scripts`, `tests`로 나누었고 실행 방법은 README에 적었습니다. 공지 원문과 분석 결과는 기존 서버의 공통 DB 테이블에 저장합니다. 관리자 화면에서 요청한 수집·재분석 작업도 처리합니다. 서버에서는 같은 DB를 사용하고, 프론트에서는 기존 공지 API를 호출하면 됩니다. 죽전·천안 학과별 공지를 추가했고, 공개 접근이 제한된 학과는 reports/에 별도로 정리했습니다. 첨부파일 내용 분석은 별도 범위입니다.
