"""크롤러 설정에서 개발 현황판용 사이트·지점 목록을 만듭니다 (네트워크/DB 없음)."""
from __future__ import annotations
import ast
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load_cafe_directory() -> dict:
    try:
        directory = json.loads((ROOT / 'data/cafe-directory.json').read_text())
        return {str(c['id']): c for c in directory['cafes']}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def catalog_entry(path: Path) -> dict:
    tree = ast.parse(path.read_text())
    config = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if not isinstance(target, ast.Name):
                continue
            try:
                config[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    cafes, urls, selections = {}, set(), {}

    def walk(value, theme=False):
        if isinstance(value, dict):
            if value.get('cafe_id'):
                cafes[str(value['cafe_id'])] = {
                    k: str(value[k]) for k in ('cafe_id', 'name', 'cafe_name', 'branch_name', 'address', 'area')
                    if value.get(k) is not None and not (theme and k == 'name')
                }
            for key, child in value.items():
                if key in ('base_url', 'site_url', 'website_url') and isinstance(child, str):
                    parsed = urlsplit(child)
                    if parsed.scheme in ('http', 'https'):
                        urls.add(f'{parsed.scheme}://{parsed.netloc}')
                walk(child, theme)
        elif isinstance(value, (tuple, list)):
            for child in value:
                walk(child, theme)

    for key in ('BRANCHES', 'BRANCH_MAP', 'SHOP_MAP', 'SITES', 'THEMES', 'BRANDS', 'LOCATION_MAP', 'MERCHANT_MAP'):
        value = config.get(key)
        walk(value, key == 'THEMES')
        if key in ('BRANCH_MAP', 'SHOP_MAP', 'MERCHANT_MAP') and isinstance(value, dict):
            selections[key] = {}
            for branch, cid in value.items():
                selections[key][str(branch)] = [str(cid['cafe_id'])] if isinstance(cid, dict) and cid.get('cafe_id') else [cid] if isinstance(cid, str) else []
                if isinstance(cid, str) and cid.isdigit():
                    meta = (config.get('CAFE_META') or {}).get(branch, {})
                    cafes[cid] = {'cafe_id': cid, **(meta if isinstance(meta, dict) else {})}
        if key == 'BRANDS' and isinstance(value, list):
            for brand in value:
                for cid in brand.get('shop_map', {}).values():
                    if isinstance(cid, str) and cid.isdigit():
                        cafes[cid] = {'cafe_id': cid}
    if config.get('CAFE_ID'):
        cid = str(config['CAFE_ID'])
        cafes[cid] = {'cafe_id': cid, **(config.get('CAFE_META') or {})}
    for key in ('BASE_URL', 'SITE_URL', 'API_URL', 'BOOKING_URL', 'BOOKING_BASE', 'RESERVE_URL', 'RESERVE_BASE', 'AJAX_URL', 'SCHEDULE_URL', 'API_BASE'):
        value = config.get(key)
        if isinstance(value, str):
            parsed = urlsplit(value)
            if parsed.scheme in ('http', 'https'):
                urls.add(f'{parsed.scheme}://{parsed.netloc}')
    directory = load_cafe_directory()
    for cid in cafes:
        if cid in directory:
            cafes[cid] = {**cafes[cid], **{k:v for k,v in directory[cid].items() if v is not None and k != 'id'}, 'cafe_id': cid}
    title = (ast.get_docstring(tree) or path.stem).strip().splitlines()[0]
    return {'id': path.stem, 'name': title, 'urls': sorted(urls),
            'cafe_ids': sorted(cafes), 'cafes': list(cafes.values()), 'selections': selections}


def main():
    target = ROOT / 'reports' / 'crawlers' / 'catalog.json'
    entries = [catalog_entry(p) for p in sorted((ROOT / 'scripts').glob('sync_*_db.py'))]
    if '--stdout' in sys.argv:
        print(json.dumps(entries, ensure_ascii=False))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    print(f'{len(entries)} crawlers; {len({cid for entry in entries for cid in entry["cafe_ids"]})} configured cafe IDs')


if __name__ == '__main__':
    main()
