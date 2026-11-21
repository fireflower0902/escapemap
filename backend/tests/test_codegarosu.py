import pytest
from scripts.sync_codegarosu_db import parse_page

PAGE = '''<h1>가로수길</h1><form name="register">
<input name="rev_days" value="2026-11-23"><input name="zizum_num" value="1">
<select name="theme_num"><option value="14">산업스파이</option></select></form>
<table class="list"><tr><td>11:00</td><td>산업스파이</td><td>84000</td>
<td><a href="javascript:fun_rev_next('149','')"><img src="../img/sub/rev_y.png"></a></td></tr>
<tr><td>12:20</td><td>산업스파이</td><td>84000</td><td><img src="../img/sub/rev_n.png"></td></tr></table>'''


def test_distinguishes_official_available_and_full():
    themes, data = parse_page(PAGE, '2026-11-23')
    assert themes == {'14': '산업스파이'}
    assert [s['status'] for s in data['14']] == ['available', 'full']
    assert 'rev_make2' not in data['14'][0]['booking_url']
    assert data['14'][1]['booking_url'] is None


@pytest.mark.parametrize('html,day', [
    (PAGE, '2026-11-24'),
    (PAGE.replace('value="1"', 'value="2"'), '2026-11-23'),
    (PAGE.replace('rev_y.png', 'unknown.png'), '2026-11-23'),
    (PAGE.replace("fun_rev_next('149','')", 'newFunction()'), '2026-11-23'),
    (PAGE.replace('<td>11:00</td>', '<td>99:00</td>'), '2026-11-23'),
])
def test_rejects_wrong_date_branch_or_unknown_state(html, day):
    with pytest.raises(ValueError):
        parse_page(html, day)
