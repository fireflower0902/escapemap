import pytest
from scripts.sync_oasisescape_db import parse_closed_schedule_ids


def test_official_empty_closed_response():
    assert parse_closed_schedule_ids(None) == set()
    assert parse_closed_schedule_ids([]) == set()
    assert parse_closed_schedule_ids(["3", 4]) == {"3", "4"}


@pytest.mark.parametrize("payload", [{}, "null", [True], [{"id": 3}]])
def test_reject_unknown_closed_response(payload):
    with pytest.raises(ValueError):
        parse_closed_schedule_ids(payload)
