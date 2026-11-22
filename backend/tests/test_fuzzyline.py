import copy
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from scripts.sync_fuzzyline_db import parse_slots

NOW = datetime(2026, 11, 22, 1, tzinfo=ZoneInfo('Asia/Seoul'))
ROW = {'roomId': 2, 'themeId': 2, 'startTime': '2026-11-22T04:05:00.000Z',
       'status': 'filling', 'remainingCapacity': 2, 'capacityMax': 7}


def test_partial_capacity_and_utc_are_handled_like_official_ui():
    slot = parse_slots([ROW], '2026-11-22', 2, 2, 'cyberpunk-city', NOW)[0]
    assert slot['time'] == '13:05'
    assert slot['status'] == 'available'
    assert slot['booking_url'] == 'https://play.fuzzyline.io/select?theme=cyberpunk-city'


@pytest.mark.parametrize('status,remaining,expected', [
    ('full', 0, 'full'), ('open', 0, 'full'), ('pre_open', 7, 'closed'),
    ('closed', 7, 'closed'), ('in_progress', 3, 'closed')])
def test_non_bookable_states(status, remaining, expected):
    row = {**ROW, 'status': status, 'remainingCapacity': remaining}
    result = parse_slots([row], '2026-11-22', 2, 2, 'cyberpunk-city', NOW)[0]
    assert result['status'] == expected
    assert result['booking_url'] is None


@pytest.mark.parametrize('field,value', [('roomId', 1), ('themeId', 3), ('status', 'unknown'),
    ('remainingCapacity', '2'), ('remainingCapacity', -1), ('remainingCapacity', 8),
    ('startTime', '2026-11-22T04:05:00'), ('startTime', '2026-11-23T04:05:00Z')])
def test_reject_identity_date_timezone_or_state_mismatch(field, value):
    row = {**ROW, field: value}
    with pytest.raises(ValueError):
        parse_slots([row], '2026-11-22', 2, 2, 'cyberpunk-city', NOW)


def test_duplicate_or_past_time_is_not_available():
    with pytest.raises(ValueError):
        parse_slots([ROW, ROW], '2026-11-22', 2, 2, 'cyberpunk-city', NOW)
    late = datetime(2026, 11, 22, 14, tzinfo=ZoneInfo('Asia/Seoul'))
    assert parse_slots([ROW], '2026-11-22', 2, 2, 'cyberpunk-city', late)[0]['status'] == 'closed'


def test_disabled_zero_capacity_slot_is_never_available():
    row = {**ROW, 'status': 'closed', 'remainingCapacity': 0, 'capacityMax': 0}
    slot = parse_slots([row], '2026-11-22', 2, 2, 'cyberpunk-city', NOW)[0]
    assert slot['status'] == 'closed'
    assert slot['booking_url'] is None
