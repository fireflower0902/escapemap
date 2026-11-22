"""실제 사이트를 하나씩 조회하되 Firestore 대신 메모리에 저장하는 smoke test.

예: .venv/bin/python scripts/check_crawlers.py xdungeon --all-branches
    .venv/bin/python scripts/check_crawlers.py --all --timeout 60
기본: 사이트별 첫 지점, 오늘 하루. 통과는 조회·파싱·저장 형태 검증이며
공식 화면과 슬롯별 대조 완료나 전체 지점 정상 동작을 뜻하지 않습니다.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime
from urllib.parse import urlsplit
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Snapshot:
    def __init__(self, id, data):
        self.id, self._data = id, data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class Document:
    def __init__(self, store, collection, id):
        self.store, self.collection, self.id = store, collection, str(id)

    def get(self):
        return Snapshot(self.id, self.store.data.get(self.collection, {}).get(self.id))

    def set(self, data, merge=False):
        target = self.store.data.setdefault(self.collection, {})
        if merge:
            existing = target.setdefault(self.id, {})
            self._merge(existing, data)
        else:
            target[self.id] = copy.deepcopy(data)
        self.store.writes.append((self.collection, self.id))

    @classmethod
    def _merge(cls, target, data):
        for key, value in data.items():
            if isinstance(value, dict) and value:
                if not isinstance(target.get(key), dict):
                    target[key] = {}
                cls._merge(target[key], value)
            else:
                target[key] = copy.deepcopy(value)

    def update(self, data):
        self.set(data, merge=True)


class Collection:
    def __init__(self, store, name, filters=()):
        self.store, self.name, self.filters = store, name, filters

    def document(self, id):
        return Document(self.store, self.name, id)

    def where(self, field, operator, value):
        return Collection(self.store, self.name, (*self.filters, (field, operator, value)))

    def stream(self):
        for id, data in self.store.data.get(self.name, {}).items():
            if all((data.get(k) == v if op == '==' else data.get(k) in v)
                   for k, op, v in self.filters):
                yield Snapshot(id, data)

    def get(self):
        return list(self.stream())


class MemoryStore:
    def __init__(self):
        self.data, self.writes = {}, []
        path = ROOT / 'escape_aggregator.db'
        if path.exists():
            with contextlib.closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as db:
                db.row_factory = sqlite3.Row
                self.data['cafes'] = {str(row['id']): dict(row)
                                      for row in db.execute('SELECT * FROM cafe')}

    def collection(self, name):
        return Collection(self, name)


def validate_store(store):
    issues, slots, statuses, cafes, theme_ids = [], [], {}, set(), set()
    per_cafe = {}
    for collection, id in store.writes:
        cid = id if collection == 'cafes' else store.data.get('themes', {}).get(id, {}).get('cafe_id') if collection == 'themes' else None
        if cid:
            per_cafe.setdefault(cid, {'themes': 0, 'slots': 0, 'statuses': {}, 'dates': []})
    for tid in {id for collection, id in store.writes if collection == 'themes'}:
        cid = store.data['themes'][tid]['cafe_id']
        name = store.data['themes'][tid].get('name')
        if not isinstance(name, str) or not name.strip():
            issues.append(f'빈 테마명: {tid}')
        per_cafe[cid]['themes'] += 1
    for day, data in store.data.get('schedules', {}).items():
        try:
            datetime.strptime(day, '%Y-%m-%d')
        except ValueError:
            issues.append(f'잘못된 날짜: {day}')
        for cid, cafe in data.get('cafes', {}).items():
            cafes.add(cid)
            cafe_counts = per_cafe.setdefault(cid, {'themes': 0, 'slots': 0, 'statuses': {}, 'dates': []})
            cafe_counts['dates'].append(day)
            for tid, theme in cafe.get('themes', {}).items():
                theme_ids.add(tid)
                if tid not in store.data.get('themes', {}):
                    issues.append(f'테마 메타데이터 누락: {tid}')
                seen = set()
                for slot in theme.get('slots', []):
                    slots.append(slot)
                    value = slot.get('time', '')
                    if not re.fullmatch(r'(?:[012]\d):[0-5]\d', value):
                        issues.append(f'잘못된 시간: {tid} {value}')
                    if value in seen:
                        issues.append(f'중복 시간: {tid} {day} {value}')
                    seen.add(value)
                    status = slot.get('status')
                    statuses[status] = statuses.get(status, 0) + 1
                    cafe_counts['slots'] += 1
                    cafe_counts['statuses'][status] = cafe_counts['statuses'].get(status, 0) + 1
                    if status not in {'available', 'full', 'closed'}:
                        issues.append(f'알 수 없는 상태: {status}')
                    url = slot.get('booking_url')
                    if status == 'available' and (not url or urlsplit(url).scheme not in {'http', 'https'}):
                        issues.append(f'예약 가능 URL 누락: {tid} {value}')
    written_themes = {id for col, id in store.writes if col == 'themes'}
    return {
        'cafes_with_slots': len(cafes), 'themes_fetched': len(written_themes),
        'themes_with_slots': len(theme_ids), 'slots': len(slots), 'statuses': statuses,
        'dates': sorted(store.data.get('schedules', {})),
        'issues': sorted(set(issues)),
        'per_cafe': per_cafe,
        'sample_themes': [store.data['themes'][id].get('name') for id in sorted(written_themes)[:8]],
    }


def run_one(name, all_branches=False, days=0, cafe_ids=None):
    os.environ['TZ'] = 'Asia/Seoul'
    os.environ['CRAWL_SEOUL_ONLY'] = 'false'
    os.environ['SKIP_META_WRITES'] = 'false'
    if hasattr(time, 'tzset'):
        time.tzset()
    # macOS의 Python은 기본 CA 파일이 없을 수 있습니다. 인증서 검증은 유지.
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    store = MemoryStore()
    import app.firestore_db as firestore
    output = io.StringIO()
    result = {'script': name, 'checked_at': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
              'scope': 'all configured branches / today' if all_branches else 'first configured branch / today',
              'days_after_today': days,
              'database': 'in-memory; local SQLite cafe metadata seed; no live Firestore access'}
    if days:
        result['scope'] += f' + {days} day(s)'
    started = time.monotonic()
    import requests
    import urllib.request
    http_calls = []
    request_original = requests.sessions.Session.request
    open_original = urllib.request.OpenerDirector.open

    def track_request(session, method, url, *args, **kwargs):
        call = {'method': method.upper(), 'host': urlsplit(url).netloc, 'path': urlsplit(url).path}
        http_calls.append(call)
        try:
            response = request_original(session, method, url, *args, **kwargs)
            call['status'] = response.status_code
            return response
        except Exception as exc:
            call['error'] = type(exc).__name__
            raise

    def track_open(opener, request, *args, **kwargs):
        url = request.full_url if isinstance(request, urllib.request.Request) else request
        method = request.get_method() if isinstance(request, urllib.request.Request) else 'GET'
        call = {'method': method, 'host': urlsplit(url).netloc, 'path': urlsplit(url).path}
        http_calls.append(call)
        try:
            response = open_original(opener, request, *args, **kwargs)
            call['status'] = response.status
            return response
        except Exception as exc:
            call['error'] = type(exc).__name__
            raise

    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(firestore, 'init_firestore', lambda *_: None))
        stack.enter_context(patch.object(firestore, 'get_db', lambda: store))
        stack.enter_context(patch.object(firestore, '_SKIP_META', False))
        stack.enter_context(patch.object(firestore, '_CRAWL_SEOUL_ONLY', False))
        # 예상치 못한 다른 경로로 Firebase 클라이언트를 생성하더라도 중단.
        stack.enter_context(patch('firebase_admin.firestore.client', side_effect=AssertionError('Live Firestore forbidden')))
        stack.enter_context(patch.object(requests.sessions.Session, 'request', track_request))
        stack.enter_context(patch.object(urllib.request.OpenerDirector, 'open', track_open))
        try:
            module = importlib.import_module('scripts.' + name)
            selected = {}
            if cafe_ids:
                from scripts.crawler_selection import select_cafes
                selected = select_cafes(module, cafe_ids)
                result['requested_cafe_ids'] = list(map(str, cafe_ids))
                result['scope'] = 'selected cafe IDs: '+', '.join(cafe_ids)+' / today + '+str(days)+' day(s)'
            if not all_branches and not cafe_ids:
                for key in ('BRANCHES', 'BRANCH_MAP', 'SHOP_MAP', 'SITES', 'BRANDS', 'MERCHANT_MAP'):
                    value = getattr(module, key, None)
                    if isinstance(value, list) and value:
                        setattr(module, key, value[:1])
                        selected[key] = value[:1]
                    elif isinstance(value, dict) and value:
                        first = next(iter(value))
                        setattr(module, key, {first: value[first]})
                        selected[key] = [str(first)]
            result['selected'] = selected
            params = inspect.signature(module.main).parameters
            kwargs = {}
            if 'days' in params:
                kwargs['days'] = days
            if 'months' in params:
                kwargs['months'] = 1
                result['scope'] += '; monthly API returns current month'
            if 'bids' in params:
                kwargs['bids'] = list(module.SHOP_MAP)
            module.main(**kwargs)
        except Exception as exc:
            result['error'] = f'{type(exc).__name__}: {exc}'
            traceback.print_exc()
    result.update(validate_store(store))
    result['http_calls'] = http_calls
    result['duration_seconds'] = round(time.monotonic() - started, 2)
    log = output.getvalue()
    result['log_errors'] = [line.strip() for line in log.splitlines()
                            if re.search(r'\[ERROR\]|Traceback|\[WARN\]', line)][:20]
    result['status'] = ('error' if result.get('error') else 'needs_review'
                        if result['issues'] or result['log_errors'] or not result['slots']
                        or any('error' in call or call.get('status', 200) >= 400 for call in http_calls)
                        else 'smoke_pass')
    return result, log


def validation_exit_code(results, allow_site_failures=False):
    from scripts.refresh_scheduled import classify_check
    failures=[r for r in results if r.get('status')!='smoke_pass']
    lines=['# 개별 크롤러 검증 결과', '', f'검증 {len(results)}개 · 통과 {len(results)-len(failures)}개 · 확인 필요 {len(failures)}개', '', '사이트 검증 실패는 성공한 수집을 뜻하지 않습니다. 원본 결과·오류는 검증 아티팩트에 보존합니다.', '']
    infrastructure=False
    for result in failures:
        details=classify_check(result);hard=details['failure_kind']=='infrastructure';infrastructure|=hard
        name=result.get('script','unknown');reason=details['reason']
        print(('::error::' if hard or not allow_site_failures else '::warning::')+name+': '+reason)
        lines.append('- '+name+': '+reason)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as stream:stream.write('\n'.join(lines)+'\n')
    return int(not results or infrastructure or (bool(failures) and not allow_site_failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sites', nargs='*', help='xdungeon, keyescape 등')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--all-branches', action='store_true')
    parser.add_argument('--cafe-id', action='append', help='크롤러 설정에서 이 카페만 검증 (반복 가능)')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--allow-site-failures', action='store_true', help='예상된 사이트 검증 실패는 경고로 기록; 실행 오류는 실패 유지')
    parser.add_argument('--days', type=int, default=0, help='오늘 이후 추가 조회 일수 (기본 0)')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports' / 'crawlers')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.days < 0 or args.timeout <= 0:
        parser.error('--days는 0 이상, --timeout은 양수여야 합니다.')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.worker:
        name = args.sites[0]
        result, log = run_one(name, args.all_branches, args.days, args.cafe_id)
        (args.output / f'{name}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        (args.output / f'{name}.log').write_text(log)
        return
    available = {p.stem for p in (ROOT / 'scripts').glob('sync_*_db.py')}
    names = sorted(available) if args.all else [s if s.startswith('sync_') else f'sync_{s}_db' for s in args.sites]
    if not names:
        parser.error('사이트 이름 또는 --all 을 지정하세요.')
    unknown = set(names) - available
    if unknown:
        parser.error(f'알 수 없는 크롤러: {sorted(unknown)}')
    results = []
    for i, name in enumerate(names, 1):
        print(f'[{i}/{len(names)}] {name}', flush=True)
        cmd = [sys.executable, __file__, name, '--worker', '--output', str(args.output), '--days', str(args.days)]
        if args.all_branches:
            cmd.append('--all-branches')
        for cafe_id in args.cafe_id or []:
            cmd += ['--cafe-id', cafe_id]
        result_path = args.output / f'{name}.json'
        if result_path.exists():
            result_path.unlink()
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, cwd=ROOT)
            if result_path.exists():
                result = json.loads(result_path.read_text())
            else:
                result = {'script': name, 'status': 'error', 'error': completed.stderr[-1500:], 'execution_failure': True}
        except subprocess.TimeoutExpired:
            result = {'script': name, 'status': 'timeout', 'timeout_seconds': args.timeout}
        result.setdefault('checked_at', datetime.now(ZoneInfo('Asia/Seoul')).isoformat())
        if args.cafe_id:
            result['requested_cafe_ids'] = args.cafe_id
            result.setdefault('scope', 'selected cafe IDs: '+', '.join(args.cafe_id))
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        history = args.output / 'history'
        history.mkdir(exist_ok=True)
        history_name = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f') + '-' + name + '.json'
        (history / history_name).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        results.append(result)
        (args.output / 'latest-run.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"  {result['status']}: {result.get('themes_fetched', 0)} themes / {result.get('slots', 0)} slots", flush=True)
    print(f'결과: {args.output}')
    return validation_exit_code(results, args.allow_site_failures)


if __name__ == '__main__':
    sys.exit(main())
