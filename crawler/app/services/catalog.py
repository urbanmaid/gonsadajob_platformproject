"""공식 학과 목록, 공유 게시판 중복 제거, 등록 설정 및 접근 점검 보고서."""

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from app.http import SourceAccessError, validate_url
from app.parsers.dankook import BoardAccessError, Document, ParseError, parse_list

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = {"AVAILABLE", "EMPTY"}
LABELS = {"AVAILABLE": "공개 공지 확인", "PARTIAL": "일부 게시판만 수집 가능", "EMPTY": "정상 빈 게시판",
          "ACCESS_DENIED": "접근 거부", "LOGIN_REQUIRED": "로그인 필요", "BOARD_NOT_DISPLAYED": "게시판 본문 미표시",
          "HOMEPAGE_NOT_LISTED": "공식 홈페이지 링크 없음", "NO_NOTICE_LINK": "공지 링크 미확인",
          "NO_PUBLIC_ITEMS": "공개 열람 가능한 글 없음", "NETWORK_ERROR": "네트워크 오류", "HTTP_ERROR": "HTTP 오류",
          "ROBOTS_DENIED": "robots 수집 불허", "ROBOTS_UNAVAILABLE": "robots 확인 실패", "ROBOTS_INVALID": "robots 형식 오류"}


def canonical_url(url):
    p = urlsplit(url)
    path = quote(unquote(p.path.rstrip('/')), safe='/-._~')
    # 두 경로는 실제 홈페이지에서 모두 관측한 별칭이다. 다른 호스트는 임의 합치지 않는다.
    for host, site in (("law.dankook.ac.kr", "law"), ("med.dankook.ac.kr", "med")):
        if p.hostname == host and re.fullmatch(r"/-\d+", path):
            path = f"/web/{site}" + path
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))


def read_catalog(path=None):
    return json.loads(Path(path or ROOT / 'config/departments.json').read_text(encoding='utf-8'))


def select_departments(catalog, campus=None, department=None):
    return [d for d in catalog['departments'] if (not campus or d['campus'] == campus)
            and (not department or department.casefold() in d['department'].casefold())]


def source_entries(departments):
    grouped = {}
    for d in departments:
        for board in d['boards']:
            if board['status'] not in PUBLIC:
                continue
            url = canonical_url(board['list_url'])
            validate_url(url)
            item = grouped.setdefault(url, {'board': board, 'departments': []})
            if d not in item['departments']:
                item['departments'].append(d)
    result = []
    for url, item in grouped.items():
        ds, board = item['departments'], item['board']
        d = ds[0]
        suffix = f" 외 {len(ds)-1}개 전공" if len(ds) > 1 else ''
        name = f"[{d['campus']}] {d['department']}{suffix} - {board['name']}"
        p = urlsplit(url)
        result.append({'server': {'name': '단국대학교 ' + p.hostname, 'base_url': f'{p.scheme}://{p.netloc}',
                                  'interface': 'HTML', 'location': '단국대학교', 'rate_limit_per_minute': 20,
                                  'crawl_allowed': True, 'access_restricted': False},
                       'name': name[:100], 'list_url': url, 'category_hint': '학과공지',
                       'crawl_interval_minutes': 180, 'parser_version': 'dku_bbs_v1', 'is_active': True})
    return result


def status_for(boards):
    good = any(b['status'] in PUBLIC for b in boards)
    if good:
        return 'PARTIAL' if any(b['status'] not in PUBLIC for b in boards) else 'AVAILABLE'
    for code in ('LOGIN_REQUIRED', 'ACCESS_DENIED', 'NETWORK_ERROR', 'HTTP_ERROR', 'ROBOTS_DENIED', 'ROBOTS_UNAVAILABLE', 'ROBOTS_INVALID', 'NO_PUBLIC_ITEMS', 'BOARD_NOT_DISPLAYED'):
        if any(b['status'] == code for b in boards):
            return code
    return boards[0]['status'] if boards else 'NO_NOTICE_LINK'


def discover_links(html, homepage_url):
    """같은 학과 홈페이지의 공지/장학/취업 메뉴만 후보로 반환. 후보는 반드시 재검증한다."""
    p = urlsplit(homepage_url)
    site = re.match(r'/(?:[a-z]{2}/)?web/[^/]+', p.path)
    scope = site.group(0) + '/' if site else '/'
    links = {}
    for a in Document(html).root.walk():
        if a.tag != 'a':
            continue
        label = ' '.join(a.text().split())
        label = re.sub(r'arrow_forward_ios|keyboard_arrow_down|expand_more', '', label).strip()
        href = a.attrs.get('href', '')
        if not href or len(label) > 60 or not re.search(r'공지|notice|취업|채용|장학|커뮤니티', label, re.I):
            continue
        if re.search(r'일정|가이드|현황|학사안내|학사정보|장학제도|연구실', label):
            continue
        url = urljoin(homepage_url, href)
        q = urlsplit(url)
        if q.hostname != p.hostname or not q.path.startswith(scope) or q.query or q.fragment or '$' in url:
            continue
        try:
            validate_url(url)
        except ValueError:
            continue
        links[canonical_url(url)] = {'name': label, 'list_url': canonical_url(url)}
    return list(links.values())


def classify(html, url):
    try:
        links = parse_list(html, url)
        return {'status': 'AVAILABLE' if links else 'EMPTY', 'public_items': len(links)}
    except BoardAccessError as exc:
        return {'status': exc.code, 'public_items': 0}
    except ParseError:
        return {'status': 'BOARD_NOT_DISPLAYED', 'public_items': 0}


def check_board(client, board):
    result = {k: board[k] for k in ('name', 'list_url')}
    try:
        html = client.get(board['list_url'])
        final_url = client.last_url or board['list_url']
        result.update(classify(html, final_url), final_url=final_url, http_status=client.last_status)
    except SourceAccessError as exc:
        result.update(status=exc.code)
    except HTTPError as exc:
        result.update(status='ACCESS_DENIED' if exc.code in (401, 403) else 'HTTP_ERROR', http_status=exc.code)
    except (URLError, TimeoutError, OSError):
        result.update(status='NETWORK_ERROR')
    except ValueError:
        result.update(status='SOURCE_POLICY_OR_DATA_INVALID')
    return result


def audit_catalog(catalog, client, *, discover=True, progress=None):
    """공유 홈페이지·게시판은 한 번 요청한다. 한 곳의 실패가 다음 학과 점검을 막지 않는다."""
    result = json.loads(json.dumps(catalog))
    result['checked_at'] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
    result['method'] = 'HTTP GET + robots.txt 준수 + 공개 목록 파싱; AI 호출/DB 쓰기 없음'
    homes, boards = {}, {}
    for d in result['departments']:
        h = d.get('homepage_url')
        if not h:
            d.update(status='HOMEPAGE_NOT_LISTED', homepage_status='HOMEPAGE_NOT_LISTED')
            continue
        # 공식 의과대학 링크의 현재 HTTPS 목적지. 임의 HTTP 전체 허용은 하지 않는다.
        fetch_url = 'https://med.dankook.ac.kr/home' if h == 'http://med.dankook.ac.kr/' else h
        if h not in homes:
            try:
                html = client.get(fetch_url)
                homes[h] = {'status': 'AVAILABLE', 'final_url': client.last_url or fetch_url,
                            'candidates': discover_links(html, client.last_url or fetch_url) if discover else []}
            except SourceAccessError as exc:
                homes[h] = {'status': exc.code, 'candidates': []}
            except HTTPError as exc:
                homes[h] = {'status': 'ACCESS_DENIED' if exc.code in (401, 403) else 'HTTP_ERROR', 'candidates': [], 'http_status': exc.code}
            except (URLError, TimeoutError, OSError):
                homes[h] = {'status': 'NETWORK_ERROR', 'candidates': []}
            except ValueError:
                homes[h] = {'status': 'SOURCE_POLICY_OR_DATA_INVALID', 'candidates': []}
        home = homes[h]
        d['homepage_status'] = home['status']
        d['checked_at'] = result['checked_at']
        # 홈페이지 실패와 게시판 실패를 혼동하지 않는다. 기존 게시판은 별도로 확인한다.
        candidates = {canonical_url(b['list_url']): b for b in home['candidates']}
        candidates.update({canonical_url(b['list_url']): b for b in d['boards']})
        checked = []
        for url, b in candidates.items():
            if url not in boards:
                boards[url] = check_board(client, {**b, 'list_url': url})
            checked.append(boards[url])
        d['boards'] = checked
        d['status'] = status_for(checked) if checked else home['status'] if home['status'] != 'AVAILABLE' else 'NO_NOTICE_LINK'
        if progress:
            progress(d)
    return result


def write_reports(catalog, prefix):
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix('.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    ds = catalog['departments']
    fields = ['campus', 'college', 'department', 'status', 'homepage_status', 'homepage_url', 'board_name', 'board_status', 'list_url']
    with prefix.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for d in ds:
            for b in d['boards'] or [{}]:
                writer.writerow({**{k:d.get(k,'') for k in fields[:6]}, 'board_name':b.get('name',''),
                                 'board_status':b.get('status',''), 'list_url':b.get('list_url','')})
    counts = Counter(d['status'] for d in ds)
    lines = ['# 단국대학교 학과 공지 접근 점검', '', f"확인 일시: {catalog['checked_at']}", '', catalog['method'], '',
             f"학과·학부·전공 {len(ds)}개 / 공개 수집 설정 {len(source_entries(ds))}개(공유 URL 중복 제거)", '',
             '| 결과 | 학과·전공 수 |', '|---|---:|']
    lines += [f"| {LABELS.get(s,s)} | {n} |" for s,n in counts.items()]
    homes = {d['homepage_url']: d.get('homepage_status') for d in ds if d.get('homepage_url')}
    lines += ['', f"고유 홈페이지 {len(homes)}곳 중 접속 확인 {sum(s == 'AVAILABLE' for s in homes.values())}곳. 학과별 공지 접근 상태는 위 표와 별도로 분류한다."]
    fallback = [d for d in ds if d.get('shared_college_notice')]
    if fallback:
        lines += ['', '학과 자체 홈페이지 링크가 없는 ' + ', '.join(d['department'] for d in fallback)
                  + '에는 [프리무스국제대학 공통 공지](' + fallback[0]['shared_college_notice'] + ')를 별도 수집 대상으로 제공한다.']
    lines += ['', '## 수집 불가 또는 일부 제한 학과', '',
              '홈페이지 자체가 열리지 않는 경우와 공지 본문 미표시·접근 거부·공식 링크 부재를 구분했습니다. 공개 목록 확인은 robots 허용, 모든 상세 글의 열람, 첨부 내용 추출을 보장하지 않습니다.', '',
              '| 캠퍼스 | 학과·전공 | 상태 | 공지/확인 주소 |', '|---|---|---|---|']
    for d in ds:
        bad = [b for b in d['boards'] if b['status'] not in PUBLIC]
        if d['status'] == 'AVAILABLE' and d.get('homepage_status') == 'AVAILABLE':
            continue
        for b in bad or [{}]:
            code = b.get('status', d['status'])
            if not b and d.get('homepage_status') not in ('AVAILABLE', None):
                code = d['homepage_status']
            label = LABELS.get(code, code)
            url = b.get('list_url') or d['homepage_url'] or d['directory_url']
            lines.append(f"| {d['campus']} | {d['department']} | {label} | [{b.get('name','확인 주소')}]({url}) |")
    lines += ['', '## 학과 전체 목록', '', '| 캠퍼스 | 단과대학 | 학과·전공 | 결과 | 공개 게시판 수 |', '|---|---|---|---|---:|']
    for d in ds:
        lines.append(f"| {d['campus']} | {d['college']} | {d['department']} | {LABELS.get(d['status'],d['status'])} | {sum(b['status'] in PUBLIC for b in d['boards'])} |")
    lines += ['', '학과 홈페이지 출처는 지원 자격과 별개입니다. 해당 학과 홈페이지에 게시되었다는 이유만으로 신청 대상을 제한하지 않습니다.', '']
    prefix.with_suffix('.md').write_text('\n'.join(lines), encoding='utf-8')
