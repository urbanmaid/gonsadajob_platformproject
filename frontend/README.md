
# 공사다잡 Frontend

단국대학교 대학생 공지사항 개인화 플랫폼

## 1. 개발 환경

- Next.js (React)
- JavaScript
- CSS Modules
- Node.js v24.22.3
- npm
- GitHub

## 2. 실행 방법

프로젝트 최상위 폴더에서 아래 명령어를 실행한다.

    cd frontend
    npm install
    npm run dev

브라우저에서 http://localhost:3000 접속

Windows PowerShell에서 npm 실행이 제한되는 경우
npm 대신 npm.cmd 사용

## 3. 구현 기능

- 메인 대시보드
- 로그인 및 회원가입 UI
- 개인화 프로필 설정
- 캠퍼스별 공지사항 필터링
- 주전공 및 복수전공 기반 필터링
- 학년 및 관심 분야 기반 필터링
- 공지사항 검색
- AI 요약 표시 영역
- 공지사항 상세 조회
- 기본 참여 자격 충족 여부 표시
- 북마크 추가 및 삭제
- 일정 및 To-do 관리
- 준비 사항 진행률 확인
- 마이페이지 및 프로필 수정
- 브라우저 내부 데이터 저장
- 반응형 UI

## 4. 페이지 경로

| URL | 기능 |
| --- | --- |
| / | 메인 화면 |
| /login | 로그인 |
| /register | 회원가입 |
| /onboarding | 개인화 설정 |
| /dashboard | 맞춤 대시보드 |
| /notices | 전체 공지사항 |
| /notices/[id] | 공지사항 상세 |
| /bookmarks | 북마크 |
| /tasks | 일정 및 To-do |
| /settings | 마이페이지 |

## 5. 주요 파일

- src/app/Dashboard.js
  - 대시보드 및 공지사항 검색, 필터링

- src/app/noticeData.js
  - 화면 구현 및 테스트용 공지사항 데이터
  - 실제 크롤링 및 AI 분석 데이터 연동 대상

- src/app/demoStorage.js
  - 북마크 및 To-do 임시 저장 기능

- src/app/onboarding/ProfileForm.js
  - 사용자 프로필 설정 및 수정

- src/app/notices/[id]/NoticeDetail.js
  - 공지사항 상세 및 기본 자격 판별

- src/app/tasks/page.js
  - 일정 및 준비 사항 관리

- src/app/login/page.js
  - 로그인 UI

- src/app/register/page.js
  - 회원가입 UI 및 입력값 검증

## 6. 현재 공지사항 데이터 구조

| 필드 | 설명 |
| --- | --- |
| id | 공지사항 고유 ID |
| title | 공지사항 제목 |
| category | 공지 분류 |
| summary | AI 요약 표시 내용 |
| source | 공지 출처 |
| date | 게시일 |
| deadline | 신청 마감일 |
| campus | 대상 캠퍼스 |
| department | 대상 학과 |
| grade | 대상 학년 |
| residence | 거주 방식 조건 |
| common | 공통 공지 여부 |
| detail | 공지 상세 내용 |

현재는 프론트엔드 테스트용 데이터 구조이며,
실제 API 응답 형식에 따라 수정할 수 있다.

추후 원문 URL, 첨부파일, 신청 방법,
세부 참여 조건, AI 분석 근거 등의 데이터가 필요하다.

## 7. 사용자 프로필 데이터 구조

| 필드 | 설명 |
| --- | --- |
| university | 소속 대학교 |
| campus | 소속 캠퍼스 |
| department | 주전공 |
| doubleMajor | 복수전공 |
| grade | 학년 |
| interests | 관심 분야 배열 |
| residence | 거주 방식 |

## 8. 임시 데이터 저장 방식

현재 localStorage를 이용하여 데이터를 저장한다.

- gonsadajob_profile : 개인화 프로필
- gonsadajob_bookmarks : 북마크
- gonsadajob_tasks : 준비 사항 및 완료 상태

실제 회원 인증 및 데이터베이스 연동 이후
사용자별 서버 저장 방식으로 변경해야 한다.

비밀번호는 브라우저에 저장하지 않는다.

## 9. 백엔드 연동 필요 항목

- 회원가입 및 로그인 인증
- 사용자 프로필 조회 및 수정
- 공지사항 목록 및 상세 조회
- 공지사항 검색 및 개인화 추천
- 북마크 조회, 추가 및 삭제
- To-do 조회, 추가, 수정 및 삭제

## 10. AI 및 크롤링 연동 필요 항목

- 단국대학교 실제 공지사항 데이터
- 공지사항 분류 및 태깅 결과
- AI 핵심 요약
- 참여 대상 및 자격 조건
- 신청 마감일 및 주요 일정
- 신청 방법 및 준비 사항
- 공식 공지 원문 URL
- 첨부파일 정보

## 11. 추후 협의 사항

- FastAPI 서버 주소
- REST API 엔드포인트
- 요청 및 응답 데이터 형식
- 회원 인증 및 권한 관리 방식
- 공지사항 ID 형식
- 날짜 형식 통일
- 학과 및 캠퍼스 데이터 형식
- 참여 자격 판별 및 추천 방식

API 경로 및 데이터 구조는 백엔드와 AI 담당자 간
협의 후 확정한다.

## 12. 현재 구현 범위

프론트엔드 1차 프로토타입 구현 단계이다.

현재 공지사항과 AI 요약은 예시 데이터이며,
실제 크롤링 및 AI 분석 시스템은 연결되지 않았다.

로그인과 회원가입은 UI 및 입력값 검증 단계이며,
실제 회원 인증 기능은 백엔드 연동이 필요하다.

개인화 필터링과 기본 자격 판별은
프론트엔드 테스트용 규칙을 적용한 상태이다.

## 13. 담당자

- 서지우 : 프론트엔드 및 UI
- 남예빈 : 기반 서버
- 박기훈 : AI 연계 및 공지사항 크롤링
- 박강 : 팀장, 프로젝트 점검 및 Merge 관리
