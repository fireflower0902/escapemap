import contextlib
import io
import json
from unittest.mock import AsyncMock, patch

import pytest

from scripts import check_crawlers, refresh_scheduled, run_supabase_crawler


def test_timeout_writes_fresh_report_and_records_failure(tmp_path):
    report = tmp_path / 'reports/crawlers/supabase/sync_example_db-1.json'
    report.parent.mkdir(parents=True)
    report.write_text('{"status":"smoke_pass","published":true}')
    publish = AsyncMock()
    with patch.object(run_supabase_crawler, 'ROOT', tmp_path), patch.object(run_supabase_crawler, 'publish', publish):
        result = run_supabase_crawler.record_timeout('sync_example_db', '1', 6)
    assert json.loads(report.read_text()) == result
    assert result['status'] == 'timeout'
    assert result['published'] is False
    publish.assert_awaited_once_with(result, None, '1', 6)
    assert refresh_scheduled.failure_details(report)['failure_kind'] == 'site'


def test_timeout_record_database_failure_remains_infrastructure(tmp_path):
    publish = AsyncMock(side_effect=ConnectionError('secret-dsn'))
    with patch.object(run_supabase_crawler, 'ROOT', tmp_path), patch.object(run_supabase_crawler, 'publish', publish):
        result = run_supabase_crawler.record_timeout('sync_example_db', '1', 6)
    report = tmp_path / 'reports/crawlers/supabase/sync_example_db-1.json'
    assert refresh_scheduled.failure_details(report)['failure_kind'] == 'infrastructure'
    assert 'secret-dsn' not in report.read_text()
    assert result['published'] is False


@pytest.mark.parametrize('result', [
    {'status': 'timeout'},
    {'status': 'error', 'error': 'ConnectionError: source unavailable'},
    {'status': 'needs_review', 'http_calls': [{'status': 403}]},
])
def test_expected_site_failures_warn_but_strict_cli_still_fails(result, tmp_path):
    summary = tmp_path / 'summary.md'
    result = {'script': 'sync_example_db', **result}
    output = io.StringIO()
    with patch.dict('os.environ', {'GITHUB_STEP_SUMMARY': str(summary)}), contextlib.redirect_stdout(output):
        assert check_crawlers.validation_exit_code([result], True) == 0
        assert check_crawlers.validation_exit_code([result]) == 1
    assert '::warning::sync_example_db' in output.getvalue()
    assert '확인 필요 1개' in summary.read_text()


@pytest.mark.parametrize('result', [
    {'status': 'error', 'error': 'NameError: broken'},
    {'status': 'error', 'error': 'ModuleNotFoundError: missing'},
    {'status': 'error', 'error': 'storage: ConnectionError'},
    {'status': 'error', 'execution_failure': True},
])
def test_real_execution_failures_are_not_suppressed(result):
    with contextlib.redirect_stdout(io.StringIO()):
        assert check_crawlers.validation_exit_code([result], True) == 1


def test_no_results_does_not_pass():
    assert check_crawlers.validation_exit_code([], True) == 1


def test_runner_parent_timeout_produces_classifiable_report(tmp_path):
    import subprocess
    import sys

    script = tmp_path / 'scripts/sync_example_db.py'
    script.parent.mkdir()
    script.write_text('')
    argv = ['run_supabase_crawler.py', 'sync_example_db', '--cafe-id', '1', '--days', '6', '--timeout', '1']
    with patch.object(run_supabase_crawler, 'ROOT', tmp_path), \
         patch.object(run_supabase_crawler, 'catalog_entry', return_value={'cafe_ids': ['1']}), \
         patch.object(run_supabase_crawler.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 1)), \
         patch.object(run_supabase_crawler, 'publish', AsyncMock()), \
         patch.object(sys, 'argv', argv):
        assert run_supabase_crawler.main() == 1
    report = tmp_path / 'reports/crawlers/supabase/sync_example_db-1.json'
    assert refresh_scheduled.failure_details(report) == {
        'failure_kind': 'site', 'reason': '사이트 수집 제한 시간 초과',
    }
