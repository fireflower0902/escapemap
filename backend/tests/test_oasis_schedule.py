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


def test_missing_theme_name_is_not_published_as_placeholder():
    from scripts.sync_oasisescape_db import parse_ticket_page
    with pytest.raises(ValueError, match="테마명 없는"):
        parse_ticket_page("<html></html>", 17)
