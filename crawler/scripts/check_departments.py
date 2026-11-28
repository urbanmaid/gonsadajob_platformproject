"""학과별 홈페이지/공지 접근 점검. DB나 AI 키 없이 실행할 수 있다."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.http import HttpClient
from app.services.catalog import ROOT, audit_catalog, read_catalog, select_departments, source_entries, write_reports


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', default=str(ROOT/'config/departments.json'))
    p.add_argument('--campus', choices=['죽전','천안'])
    p.add_argument('--department', help='학과명 부분 일치')
    p.add_argument('--offline', action='store_true', help='포함된 브라우저 확인 결과로 보고서만 재생성')
    p.add_argument('--no-discover', action='store_true', help='기등록 게시판만 확인')
    p.add_argument('--output', default='reports/department_access_latest', help='확장자 없는 보고서 경로')
    p.add_argument('--sources-output', help='접근 가능한 게시판의 관리자 API 등록 JSON 저장 경로')
    args=p.parse_args(argv)
    catalog=read_catalog(args.catalog)
    catalog['departments']=select_departments(catalog,args.campus,args.department)
    if not catalog['departments']:
        p.error('조건에 맞는 학과가 없습니다.')
    if not args.offline:
        s=Settings.from_env()
        catalog=audit_catalog(catalog,HttpClient(s.user_agent,s.timeout,s.request_interval),discover=not args.no_discover,
                              progress=lambda d:print(json.dumps({k:d[k] for k in ('campus','department','status')},ensure_ascii=False),flush=True))
    write_reports(catalog,args.output)
    if args.sources_output:
        path=Path(args.sources_output); path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(source_entries(catalog['departments']),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(Path(args.output).with_suffix('.md')),'departments':len(catalog['departments']),
                      'public_boards':len(source_entries(catalog['departments'])),'live_check':not args.offline},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
