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

## Windows 실습 (PowerShell)

이 문서의 1~8단계를 따르면 **기본 테스트 → 실제 공지 미리 보기 → 로컬 DB 저장 → 서버 API 조회**까지 확인할 수 있다. 처음에는 각자 PC의 SQLite를 사용하며 Supabase 계정과 OpenAI 키는 필요하지 않다. AI 분석은 10단계에서 선택적으로 실행한다.

- 권장 환경: Windows 10/11, Python 3.14, Windows PowerShell 5.1 또는 PowerShell 7.
- 아래 `powershell` 블록은 **PowerShell 창에 한 블록씩 붙여 넣는다.** CMD/Git Bash에 섞어 넣지 않는다.
- 가상환경의 `python.exe`를 직접 실행하므로 `Activate.ps1` 실행이나 실행 정책 변경은 필요하지 않다.
- 오류가 나오면 다음 블록을 실행하지 않는다. `if ($LASTEXITCODE -ne 0)`은 Python 명령 실패를 확인한다.
- 이 절차는 각자 PC에서 독립적으로 재현한다. 한 팀원이 수집한 로컬 DB가 다른 팀원에게 자동으로 공유되지는 않는다.
- **검증 범위:** Python 3.14.10/macOS에서 크롤러 테스트 54개, 오프라인 데모, 서버 공통 8개 테이블 컬럼 비교를 확인했다. Windows/PowerShell에서의 실제 실행, 서버 패키지 설치 및 실시간 HTTP/OpenAI/Supabase 통합은 이 문서의 성공 기준에 따라 팀 환경에서 추가 검증해야 한다.

### 1. 저장소와 Python 준비

1. [func_crawler 브랜치](https://github.com/urbanmaid/gonsadajob_platformproject/tree/func_crawler)를 연다. PR 병합 전에도 이 브랜치로 실습할 수 있다.
2. **Code → Download ZIP → 모두 압축 풀기**로 저장소 전체를 내려받는다. ZIP 안에서 직접 실행하거나 `crawler`만 따로 옮기지 않는다.
3. 압축을 푼 폴더 중 **`crawler`, `server`, `frontend`가 바로 안에 있는 폴더**가 프로젝트 루트다. 탐색기의 주소 표시줄을 클릭해 이 폴더의 실제 경로를 복사한다. Downloads/Documents/OneDrive 위치나 폴더 이름을 임의로 가정하지 않는다.
4. 시작 메뉴에서 **PowerShell**을 열고 아래 명령을 실행한다.

```powershell
py -3.14 --version
```

`Python 3.14.x`가 나와야 한다. 설치되어 있지 않다면 [Python 공식 다운로드](https://www.python.org/downloads/windows/)에서 Python install manager를 설치하고 PowerShell을 새로 연다. 설치 관리자를 사용하는 경우 `pymanager install 3.14`로 3.14를 설치한 뒤 위 명령을 다시 확인한다. [공식 Windows 설치 안내](https://docs.python.org/3.14/using/windows.html)도 참고한다.

Git이 설치되어 있다면 ZIP 대신 `git clone --branch func_crawler https://github.com/urbanmaid/gonsadajob_platformproject.git`을 사용할 수 있다. 이미 작업 중인 폴더를 덮어쓰지 않는다. ZIP으로 받은 폴더에는 Git 메타데이터가 없으므로 `git switch`나 `git pull`을 실행하지 않는다.

### 2. PowerShell A: 실제 경로 확인

첫 번째 창을 **PowerShell A**라고 한다. 아래 블록을 실행한 뒤 경로를 물으면 1단계에서 복사한 **프로젝트 루트 경로**를 입력한다. `crawler`나 `server`까지 붙이지 않는다.

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$projectRoot = (Read-Host "프로젝트 루트 폴더의 실제 경로").Trim().Trim('"')
```

경로를 입력하고 Enter를 누른 뒤, 다음 블록을 실행한다.

```powershell
$projectRoot = (Resolve-Path -LiteralPath $projectRoot).Path
foreach ($relative in @("crawler\app\main.py", "crawler\tests", "crawler\.env.example", "crawler\.gitignore", "server\app\main.py", "server\.env.example")) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative))) {
        throw "필수 파일 또는 폴더가 없습니다: $relative / 압축 해제 위치와 브랜치를 확인하세요."
    }
}
Set-Location -LiteralPath $projectRoot
Get-Location
```

마지막에 탐색기에서 복사한 경로가 표시되면 성공이다. `$projectRoot`는 이 창에만 저장된다. 새 창에서는 5단계처럼 다시 설정한다.

### 3. PowerShell A: 크롤러 기본 테스트

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot "crawler")
py -3.14 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "크롤러 가상환경 생성 실패" }
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "크롤러 테스트 실패: 위 오류를 확인하세요." }
& .\.venv\Scripts\python.exe scripts\check_server_contract.py
if ($LASTEXITCODE -ne 0) { throw "서버와 크롤러의 컬럼 정의가 다릅니다." }
```

현재 2차 구현본 기준 성공 결과:

```text
Ran 54 tests in ...
OK
OK: 기반 서버 공통 8개 테이블의 컬럼 이름 일치
```

이어서 데모와 샘플 파싱을 확인한다.

```powershell
& .\.venv\Scripts\python.exe scripts\demo_pipeline.py
if ($LASTEXITCODE -ne 0) { throw "오프라인 데모 실패" }
& .\.venv\Scripts\python.exe -m app.main preview --fixture
if ($LASTEXITCODE -ne 0) { throw "샘플 파싱 실패" }
```

| 데모 출력 | 의미 |
|---|---|
| `mode: OFFLINE_FIXTURE`, `real_api_called: false` | 합성 자료 사용, 실제 AI 호출 없음 |
| 수집 작업 `SUCCEEDED` | 데모 공지 처리 성공 |
| `repeat_save: unchanged` | 같은 내용을 다시 저장해도 중복 생성하지 않음 |
| `notice_count: 1`, `current_analysis_count: 1` | 공지와 현재 분석 각 1건 유지 |
| 분석 작업 `REVIEW_REQUIRED` | 첨부·이미지의 추가 확인 필요. 데모 실패가 아님 |

데모는 메모리 DB를 사용하며 `server/dev.db`에 샘플 공지를 넣지 않는다. 크롤러의 오프라인 테스트와 SQLite 실행은 표준 라이브러리로 가능하므로 이 단계에서는 `crawler/requirements.txt` 설치가 필요하지 않다. 컬럼 비교는 정적 검사이며 실제 API/DB 통합 검사를 대신하지 않는다.

### 4. PowerShell A: 서버 준비와 실행

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot "server")
py -3.14 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "서버 가상환경 생성 실패" }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "서버 패키지 설치 실패: 설치 로그를 확인하세요." }
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "서버 테스트 실패: 위 오류를 확인하세요." }
```

서버 테스트는 `passed`이고 실패가 없어야 한다. 크롤러의 54개 테스트와는 별도다.

처음 복사한 `server/.env.example`은 아래 로컬 설정을 제공한다. 기존 `.env`가 있다면 `notepad .env`로 확인한다. 기존 팀 공용 설정을 이 실습을 위해 덮어쓰기보다 별도로 내려받은 실습 폴더를 사용한다.

```dotenv
ENVIRONMENT=development
DATABASE_URL=sqlite:///./dev.db
AUTO_CREATE_TABLES=true
SUPABASE_URL=
NOTICES_PUBLIC=true
```

`JWT_SECRET`은 개발 토큰 발급에 필요하므로 예시 파일의 값을 지우지 않는다. 이 예시 키는 로컬 개발용이며 실제 Supabase/운영 환경에서는 사용하지 않는다.

아래 검사로 로컬 DB 설정인지 확인한 뒤 서버를 실행한다.

```powershell
& .\.venv\Scripts\python.exe -c "from app.config import get_settings; s=get_settings(); assert s.environment == 'development' and s.database_url == 'sqlite:///./dev.db' and not s.supabase_url and s.auto_create_tables and s.notices_public and bool(s.jwt_secret), 'Check server/.env: local SQLite development settings required'; print('OK: local SQLite settings')"
if ($LASTEXITCODE -ne 0) { throw "server/.env의 로컬 실습 설정을 확인하세요." }
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`Application startup complete.`가 표시되면 브라우저에서 [서버 상태](http://127.0.0.1:8000/health)를 연다.

```json
{"status":"ok","database":true,"environment":"development"}
```

서버 시작 시 `server/dev.db`와 필요한 테이블이 만들어진다. **PowerShell A는 서버가 실행된 채로 둔다. 이후 작업은 새 PowerShell B에서 한다.** `/health`에는 `/api/v1`을 붙이지 않는다.

### 5. PowerShell B: 관리자 토큰과 DB 연결

새 PowerShell 창을 열고 아래 블록을 실행한다. 경로를 물으면 A에서 사용한 것과 **같은 프로젝트 루트**를 입력한다.

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$projectRoot = (Read-Host "A와 같은 프로젝트 루트 폴더의 실제 경로").Trim().Trim('"')
```

경로를 입력하고 Enter를 누른 뒤, 다음 블록을 실행한다.

```powershell
$projectRoot = (Resolve-Path -LiteralPath $projectRoot).Path
$serverPython = Join-Path $projectRoot "server\.venv\Scripts\python.exe"
$crawlerPython = Join-Path $projectRoot "crawler\.venv\Scripts\python.exe"
foreach ($executablePath in @($serverPython, $crawlerPython)) {
    if (-not (Test-Path -LiteralPath $executablePath)) { throw "가상환경을 찾을 수 없습니다: $executablePath" }
}
Set-Location -LiteralPath (Join-Path $projectRoot "server")
$adminToken = & $serverPython scripts\make_dev_token.py --admin
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$adminToken)) {
    throw "개발용 관리자 토큰 발급 실패: server/.env를 확인하세요."
}
$env:ADMIN_ACCESS_TOKEN = ([string]$adminToken).Trim()
Set-Location -LiteralPath (Join-Path $projectRoot "crawler")
$env:DATABASE_URL = "sqlite:///../server/dev.db"
$env:API_BASE_URL = "http://127.0.0.1:8000/api/v1"
$env:PAGES_PER_BOARD = "1"
$env:NOTICES_PER_BOARD = "2"
$env:ANALYSES_PER_CYCLE = "1"
& $crawlerPython -m app.main check
if ($LASTEXITCODE -ne 0) { throw "DB 연결 또는 테이블 확인 실패" }
```

정상 결과:

```json
{"database":"sqlite","common_tables":8,"status":"OK"}
```

| 실행 위치 | DB 주소 | 실제 사용하는 파일 |
|---|---|---|
| `server` | `sqlite:///./dev.db` | 프로젝트 루트의 `server/dev.db` |
| `crawler` | `sqlite:///../server/dev.db` | 위와 같은 파일 |

이 블록의 `$env:` 값은 **B 창에만 적용되며 `.env`보다 우선**한다. 관리자 토큰은 출력하거나 파일에 쓰지 않는다. 창을 닫거나 토큰 기본 유효기간 24시간이 지나면 5단계를 다시 실행한다. 서버의 `JWT_SECRET`을 바꾼 경우에는 서버를 재시작하고 토큰도 다시 발급한다.

### 6. PowerShell B: 실제 공지 1건 미리 보기

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot "crawler")
& $crawlerPython -m app.main preview --url https://cms.dankook.ac.kr/web/ace/notice --limit 1
if ($LASTEXITCODE -ne 0) { throw "실제 홈페이지 미리 보기 실패: 오류 코드를 확인하세요." }
```

실제 공지의 제목·본문·원문 주소가 JSON으로 표시되는지 확인하고 원문 링크와 비교한다. **출력이 없으면 공지 수집 성공으로 판단하지 않는다.** 이 명령은 DB 저장·AI 호출을 하지 않는다. 브라우저에서 열리는 사이트도 HTTP 자동 수집에서는 robots 정책이나 접근 제한에 걸릴 수 있다.

### 7. PowerShell B: 게시판 등록과 실제 저장

처음에는 컴퓨터공학과만 등록한다.

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot "crawler")
& $crawlerPython scripts\register_sources.py --department "컴퓨터공학과" --apply
if ($LASTEXITCODE -ne 0) { throw "수집 대상 등록 실패: 서버 실행과 관리자 인증을 확인하세요." }
& $crawlerPython -m app.main run-once --crawl-only --department "컴퓨터공학과" --max-jobs 3
if ($LASTEXITCODE -ne 0) { throw "수집 실패 또는 일부 실패: 출력된 작업 상태와 errors를 확인하세요." }
```

등록의 `CREATED`는 신규 등록, `SKIPPED_EXISTING`은 같은 URL이 이미 있어 건너뛴 것이다. `--apply`를 빼면 등록 예정 JSON만 출력하고 실제 등록하지 않는다.

| 출력 | 확인 기준 |
|---|---|
| 수집 작업 `SUCCEEDED` | 해당 작업 처리 성공 |
| `fetched_count` | 읽은 공지 수. 정상 빈 게시판에서는 0일 수 있음 |
| `created_count` / `updated_count` | 새 공지 / 변경 내용 저장 수. 기존 동일 공지는 새로 만들지 않음 |
| `errors`, `PARTIAL`, `FAILED` | 실패 이유를 확인할 것 |

`--max-jobs 3`은 **게시판 작업 최대 3개**이고, 공지 수는 B의 `NOTICES_PER_BOARD=2`가 제한한다. `--crawl-only`이므로 AI는 호출하지 않고 분석 작업을 `PENDING`으로 남긴다. 한 DB에서는 크롤러 워커 하나만 실행한다.

### 8. 브라우저에서 API 결과 확인

1. [API 테스트 화면](http://127.0.0.1:8000/docs)을 연다.
2. `GET /api/v1/notices` → **Try it out → Execute**. HTTP 200과 `items` 안의 실제 수집 공지를 확인한다.
3. 공지의 `id`를 복사한다.
4. `GET /api/v1/notices/{notice_id}` → **Try it out** → 복사한 `id` 입력 → **Execute**.
5. 제목·본문·원문 주소·첨부 정보를 원문과 비교한다. AI 실행 전 요약이 비어 있는 것은 정상이다.

관리자 작업 기록을 확인하려면 B에서 아래 명령으로 토큰을 클립보드에 복사한다.

```powershell
$env:ADMIN_ACCESS_TOKEN | Set-Clipboard
```

`/docs` 오른쪽 위 **Authorize**에 붙여 넣고 인증한다. `Bearer `는 직접 붙이지 않는다. 이후 `GET /api/v1/admin/crawl-jobs`, `GET /api/v1/admin/analysis-jobs`를 실행한다. 기본 로컬 설정에서는 일반 공지 목록·상세 조회에 이 인증이 필요하지 않다.

**완료 기준:** 기본 테스트 통과 + `/health` 정상 + 실제 공지 저장 + `/api/v1/notices` 및 상세 API에서 확인. 이것은 크롤러·서버 연동 확인이며, 프론트의 샘플 데이터를 실제 API로 교체하는 작업은 프론트 담당 영역이다.

### 9. 전체 학과 접근 점검과 수집 확대

PowerShell B에서 실행한다. `--offline`은 포함된 과거 점검 자료로 보고서를 다시 만드는 옵션이며 실시간 접속 검사가 아니다.

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot "crawler")
& $crawlerPython scripts\check_departments.py --department "컴퓨터공학과" --output reports/computer_engineering_live
if ($LASTEXITCODE -ne 0) { throw "학과 점검 스크립트 오류" }
Invoke-Item .\reports\computer_engineering_live.csv
```

전체 학과의 현재 접근 상태를 확인하려면:

```powershell
& $crawlerPython scripts\check_departments.py --output reports/department_access_live
if ($LASTEXITCODE -ne 0) { throw "전체 점검 스크립트 오류" }
Invoke-Item .\reports\department_access_live.csv
```

JSON·CSV·Markdown 보고서가 생성된다. 스크립트가 끝났다는 사실과 모든 학과의 접속 성공은 다르므로 **보고서 안의 상태와 사유**를 확인한다. CSV 연결 프로그램이 없으면 `notepad .\reports\department_access_live.md`로 Markdown 파일을 읽는다.

전체 수집 대상 등록 후 한 번 실행:

```powershell
& $crawlerPython scripts\register_sources.py --apply
if ($LASTEXITCODE -ne 0) { throw "전체 수집 대상 등록 실패" }
& $crawlerPython -m app.main run-once --crawl-only --max-jobs 200
if ($LASTEXITCODE -ne 0) { throw "실패한 작업의 상태와 사유를 확인하세요." }
```

기본 설정 대상은 공개 학과 게시판 161개와 일반·공통 게시판 5개다. 접근 제한 학과는 목록과 보고서에 남기되 활성 수집 대상에서 제외한다. B 창의 게시판당 2건 제한은 계속 적용되며 과거 공지 전체 다운로드를 의미하지 않는다. 전체 실행은 요청 간격 때문에 오래 걸릴 수 있다.

학과 게시판의 기본 수집 주기는 180분이다. 바로 다시 실행하면 처리할 작업이 없을 수 있다. 즉시 재수집이 필요하면 관리자 인증 후 `POST /api/v1/admin/crawl-jobs`에 `{"board_id":"등록 결과의 실제 게시판 UUID"}`를 보내고 아래를 실행한다. `{}`는 활성 게시판 전체 요청이므로 특정 게시판 테스트에는 실제 ID를 넣는다.

```powershell
& $crawlerPython -m app.main run-once --no-schedule --crawl-only --max-jobs 3
```

기존 같은 `list_url`은 등록 시 건너뛰며 같은 `base_url`의 서버를 재사용한다. 기존 대상의 활성 상태·주소·파서 변경은 관리자 API `PATCH /api/v1/admin/sources/{id}`로 반영한다.

### 10. 실제 AI 분석 (선택)

OpenAI API 키가 있는 경우에만 진행하며 실제 API 사용 요금이 발생한다. B의 `ANALYSES_PER_CYCLE=1` 설정으로 대기 분석을 최대 1건 처리한다.

```powershell
Set-Location -LiteralPath (Join-Path $projectRoot "crawler")
notepad .env
```

기존 `OPENAI_API_KEY=` 줄에 본인의 키를 입력하고 저장한다. 파일 이름은 `.env.txt`가 아닌 `.env`, 인코딩은 **UTF-8(BOM 없음)**으로 유지한다. 같은 설정 키를 중복해서 추가하지 않는다. 현재 로더는 UTF-8 텍스트를 읽으며, PowerShell 5.1의 `>`/`Out-File` 기본 인코딩과 맞지 않을 수 있으므로 이 방법으로 `.env`를 만들지 않는다.

```dotenv
OPENAI_API_KEY=본인의_API_키
OPENAI_MODEL=gpt-4o-mini
```

```powershell
& $crawlerPython -m app.main run-once --analysis-only
if ($LASTEXITCODE -ne 0) { throw "AI 분석 실패: 분석 작업의 오류 코드를 확인하세요." }
```

분석 작업 목록에서 처리된 공지를 확인하고 해당 상세 API에서 요약·분류·조건·일정을 확인한다. `REVIEW_REQUIRED`는 원문·첨부 확인이 필요한 상태다. PDF/HWP/HWPX 본문 추출과 이미지 OCR은 포함하지 않는다. 키가 비어 있으면 실제 분석은 생략되고 대기 작업이 유지된다. 분석 큐는 공통이므로 학과 선택 옵션을 붙이지 않는다.

### 11. 종료와 다음 실행

- A에서 **Ctrl+C**를 눌러 서버를 종료한다. DB는 `server/dev.db`에 남는다.
- 다음 실행 때는 A에서 2단계로 경로를 설정하고 `server`로 이동한 뒤 4단계의 서버 실행 명령을 사용한다. 가상환경·패키지 설치는 처음 준비하거나 의존성이 변경됐을 때 필요하다.
- B는 새로 열 때마다 5단계를 실행한다. 그러면 토큰·소규모 수집 설정을 다시 적용한다.
- 수집 중 Ctrl+C로 중단해 `RUNNING` 작업이 남았다면 다른 워커가 종료된 것을 확인하고 B에서 `& $crawlerPython -m app.main recover`를 실행한다. 중단 작업을 `FAILED`로 마감하며 자동 재시도하지 않는다. 필요한 작업은 관리자 API에서 다시 요청한다.
- 지속 수집은 B에서 `& $crawlerPython -m app.main run --crawl-only`로 실행하고 Ctrl+C로 멈춘다. DB 파일을 삭제하는 방식으로 매번 초기화할 필요는 없다.

### 12. 자주 발생하는 오류

| 증상 | 확인·조치 |
|---|---|
| 경로를 찾을 수 없음 / `Start directory is not importable: tests` | 압축을 완전히 풀었는지, 루트 바로 아래 `crawler`·`server`가 있는지 확인. 2단계 또는 5단계의 실제 경로를 다시 입력 |
| `py` 또는 Python 3.14를 찾을 수 없음 | 1단계의 공식 설치 절차 후 새 PowerShell 창에서 확인 |
| `source`를 인식하지 못함 / `&&` 구문 오류 | Git Bash/macOS 명령을 PowerShell에 넣은 경우. 이 문서의 `powershell` 블록 사용 |
| `Activate.ps1` 실행이 차단됨 | 활성화 대신 이 문서의 `.venv\Scripts\python.exe` 직접 실행 방식 사용 |
| `.env.example` 또는 `.gitignore` 없음 | `func_crawler`의 최신 전체 파일을 받았는지 확인. 두 파일은 저장소에 포함되어야 함 |
| `No module named fastapi` / `pytest` | `server`의 가상환경으로 서버 `requirements.txt` 설치. 크롤러 가상환경과 혼동하지 않기 |
| `No module named app` | `Get-Location` 확인. 서버 명령은 `server`, 크롤러 명령은 `crawler`에서 실행 |
| `.env` 파싱 오류 / 설정 미반영 | UTF-8(BOM 없음), `.env.txt` 여부, 중복 키 확인. B의 `$env:` 값은 파일보다 우선하며 새 창에는 유지되지 않음 |
| 서버 패키지 설치 실패 | Python 버전과 설치 로그 확인. DNS·프록시·패키지 다운로드 문제인지 구분 |
| 연결 거부 / `Connection refused` | A가 실행 중인지, `http://127.0.0.1:8000/health`가 열리는지 확인 |
| DB 파일·테이블 없음 | 서버를 먼저 실행. 5단계의 DB 주소와 두 명령의 실행 폴더 확인 |
| 관리자 API 401/403 | 5단계로 관리자 토큰 재발급. API 주소와 서버 JWT 설정 일치 여부 확인 |
| 8000 포트 사용 중 | 본인이 앞서 실행한 서버 창을 확인해 종료. 다른 프로그램을 임의로 강제 종료하지 않기 |
| `URLERROR` / `SOURCE_HTTP_403/429` / robots 관련 오류 | 출력 코드와 접근 보고서 확인. DNS·사이트 응답·수집 정책을 구분하고 접근 제한을 우회하지 않기 |
| 실행했는데 작업이 0개 | 대상 등록·활성 상태·수집 주기 확인. 필요하면 9단계의 수동 작업 요청 사용 |
| `REVIEW_REQUIRED` | 첨부·이미지 또는 불명확한 조건을 사람이 확인해야 함. 테스트 실패와 구분 |

오류를 공유할 때는 **단계 번호, 실행 명령, Python 버전, 오류 코드**를 함께 남긴다. 토큰·API 키·DB 접속 비밀번호가 들어 있는 `.env` 내용은 공유하지 않는다. `.env`, `.venv`, `dev.db`는 GitHub에 올리지 않고 `.env.example`, `.gitignore`는 함께 관리한다.

## macOS와 Git Bash 참고

Windows 팀원은 위 PowerShell 절차를 사용한다. 아래는 다른 셸의 기본 테스트 명령이며, 먼저 실제 프로젝트의 `crawler` 폴더로 이동한 상태에서 실행한다. 다른 사람의 절대 경로를 그대로 복사하지 않는다.

### macOS (zsh/bash)

```bash
test -f app/main.py && test -d tests &&
python3.14 -m venv .venv &&
./.venv/bin/python -m unittest discover -s tests -v &&
./.venv/bin/python scripts/demo_pipeline.py
```

서버용 가상환경은 `server`에서 따로 생성한다. macOS의 Python 경로는 `.venv/bin/python`, Windows는 `.venv/Scripts/python.exe`이다. 서버 준비 → 관리자 토큰 → 동일 DB 연결 → 수집 → API 확인 순서는 동일하다.

### Git Bash (Windows)

```bash
test -f app/main.py && test -d tests &&
py -3.14 -m venv .venv &&
./.venv/Scripts/python.exe -m unittest discover -s tests -v &&
./.venv/Scripts/python.exe scripts/demo_pipeline.py
```

공식 참고: [Python 가상환경](https://docs.python.org/3/library/venv.html), [PowerShell 인코딩](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding), [PowerShell 명령 연결 연산자](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_pipeline_chain_operators).


## Supabase 연결

개별 로컬 실습을 마친 뒤 팀 공용 DB를 연결할 때 진행한다. 위 PowerShell B의 `DATABASE_URL` 환경변수는 `.env`보다 우선하므로 B를 닫고 새 창에서 팀 설정을 적용한다. 이때 5단계의 로컬 SQLite 설정 블록을 다시 실행하지 않는다. 크롤러 가상환경에서 `requirements.txt`를 설치하고, 실제 팀 서버의 `API_BASE_URL`·관리자 토큰·전용 DB 주소를 로컬 `.env`에 설정한다.

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

- 기존 서버의 `/api/v1/notices`, `/api/v1/notices/{id}`, `/api/v1/notices/{id}/eligibility`를 사용한다.
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
