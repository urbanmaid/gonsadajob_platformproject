## 공지 크롤러·AI 분석

담당 : 박기훈

단국대학교 죽전·천안 캠퍼스의 학과별 공지 수집과
공통 DB 저장, AI 요약·조건·일정 분석을 담당

- [크롤러 실행 및 기본 테스트](crawler/README.md)
- [학과별 공지 수집·점검 방법](crawler/docs/departments.md)
- [서버·프론트 연동 안내](crawler/docs/integration.md)
- [학과별 접근 제한 및 전체 점검 결과](crawler/reports/department_access_2026-11-29.md)
- [검증 결과와 미검증 항목](crawler/docs/verification.md)

Python 3.12 이상에서 오프라인 테스트와 데모를 실행 가능
기본 테스트에는 DB 계정과 OpenAI API 키가 필요하지 않음
실제 공지 저장은 서버 실행 및 DB 연결 설정 후 진행

현재 프론트의 예시 데이터를 실제 수집 결과로 표시하려면
서버 공지 API 연동이 추가로 필요
