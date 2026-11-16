"""전국 수집의 부분 실패와 서비스 장애를 구분한다. 누락된 작업은 성공으로 취급하지 않는다."""
import argparse
import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def evaluate(reports, manifest, shards=12, minimum_percent=90):
    expected = {(r['script'], r['cafe_id']) for r in manifest}
    errors, warnings, rows = [], [], []
    if len(reports) != shards or {r.get('shard') for r in reports} != set(range(shards)):
        errors.append('분할 작업 결과 누락 또는 중복')
    for report in reports:
        batch = report.get('results', [])
        if report.get('total') != len(batch) or report.get('published') != sum(r.get('status') == 'published' for r in batch):
            errors.append('분할 작업 합계 불일치')
        rows.extend(batch)
    keys = [(r.get('script'), r.get('cafe_id')) for r in rows]
    if set(keys) != expected or len(keys) != len(expected):
        errors.append('정기 수집 대상 누락 또는 중복')
    published = sum(r.get('status') == 'published' for r in rows)
    failures = [r for r in rows if r.get('status') != 'published']
    if not expected or published * 100 < len(expected) * minimum_percent:
        errors.append(f'정상 저장률 {minimum_percent}% 미만')
    if any(r.get('failure_kind') != 'site' for r in failures):
        errors.append('DB/실행 오류 또는 분류되지 않은 실패')
    if failures:
        warnings.append(f'{len(failures)}개 카페 수집 실패 — 정상 저장된 카페와 별도로 확인 필요')
    return {'status': 'failure' if errors else 'partial' if failures else 'success',
            'total': len(expected), 'published': published, 'failed': len(failures),
            'errors': errors, 'warnings': warnings, 'failures': failures}


def markdown(result):
    lines = ['# 전국 예약 시간표 수집 결과', '',
             f"상태: **{result['status']}** · 대상 {result['total']} · 정상 저장 {result['published']} · 실패 {result['failed']}", '',
             '개별 사이트 실패는 DB의 실패 상태와 아래 목록에 유지합니다. DB/실행 오류, 결과 누락, 정상 저장률 90% 미만은 전체 실행을 실패 처리합니다.', '']
    lines += ['- ' + text for text in result['errors'] + result['warnings']]
    if result['failures']:
        lines += ['', '| 수집기 | 카페 ID | 원인 |', '|---|---|---|']
        for row in result['failures']:
            lines.append(f"| {row['script']} | {row['cafe_id']} | {row.get('reason', '분류되지 않은 실패')} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reports', type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(p.read_text()) for p in sorted(args.reports.rglob('shard-*.json'))]
    manifest = json.loads((ROOT / 'data/scheduled-crawlers.json').read_text())
    result = evaluate(reports, manifest)
    result['checked_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = ROOT / 'reports/scheduled-summary'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    content = markdown(result)
    (output / 'README.md').write_text(content)
    print(content)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(content)
    for text in result['errors']:
        print('::error::' + text)
    for text in result['warnings']:
        print('::warning::' + text)
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
