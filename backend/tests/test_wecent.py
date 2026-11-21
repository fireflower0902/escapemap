import copy
import pytest
from scripts.sync_wecent_db import parse_availability, parse_themes

THEME = {'short_name': '아바타'}
PAYLOAD = {'date': '2026-11-23', 'branch': {'id': 1, 'name': '홍대점'},
           'theme': {'id': 1, 'name': '아바타'}, 'is_bookable_date': True,
           'slots': [{'time': '14:50', 'available': False, 'is_closed': True, 'reason': 'closed'},
                     {'time': '16:20', 'available': True, 'is_closed': False, 'reason': None},
                     {'time': '17:50', 'available': False, 'is_closed': False, 'reason': 'reserved'}]}


def test_available_reserved_and_closed_are_distinct():
    rows = parse_availability(PAYLOAD, '2026-11-23', '1', THEME)
    assert [r['status'] for r in rows] == ['closed', 'available', 'full']
    assert rows[0]['booking_url'] is None
    assert rows[1]['booking_url'] == 'https://wecent.kr/reservation'


@pytest.mark.parametrize('change', ['date', 'branch', 'theme', 'unknown_reason', 'conflict', 'boolean', 'duplicate', 'preview'])
def test_reject_wrong_or_ambiguous_availability(change):
    data = copy.deepcopy(PAYLOAD)
    if change == 'date': data['date'] = '2026-11-24'
    elif change == 'branch': data['branch']['id'] = 2
    elif change == 'theme': data['theme']['name'] = '다른 테마'
    elif change == 'unknown_reason': data['slots'][0]['reason'] = 'unknown'
    elif change == 'conflict': data['slots'][1]['is_closed'] = True
    elif change == 'boolean': data['slots'][1]['available'] = 'true'
    elif change == 'duplicate': data['slots'].append(data['slots'][0])
    elif change == 'preview': data['is_bookable_date'] = False
    with pytest.raises(ValueError):
        parse_availability(data, '2026-11-23', '1', THEME)


def test_unopened_date_does_not_create_slots():
    data = copy.deepcopy(PAYLOAD)
    data.update(is_bookable_date=False, slots=[])
    assert parse_availability(data, '2026-11-23', '1', THEME) == []


def test_theme_title_comes_from_official_page():
    html = '''<h1>Wecent Immersive</h1><button data-theme-id="1" data-branch-id="1">
    <span class="theme-copy"><strong>아바타</strong><span>75분</span><p>[아득히 바라던 타오름에 대하여]</p></span></button>'''
    theme = parse_themes(html)['1']
    assert theme['name'] == '아바타 [아득히 바라던 타오름에 대하여]'
    assert theme['duration_min'] == 75
