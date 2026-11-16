import json
import tempfile
import unittest
import contextlib
import io
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from scripts import refresh_scheduled, summarize_scheduled


class ScheduledHealthTests(unittest.TestCase):
    def reports(self, count=100, failed=0, kind='site'):
        manifest = [{'script': 'sync_example_db', 'cafe_id': str(i)} for i in range(count)]
        rows = [{**r, 'status': 'failed' if i < failed else 'published', **({'failure_kind': kind} if i < failed else {})}
                for i, r in enumerate(manifest)]
        reports = [{'shard': shard, 'results': rows[shard::12], 'total': len(rows[shard::12]),
                    'published': sum(r['status'] == 'published' for r in rows[shard::12])} for shard in range(12)]
        return reports, manifest

    def test_individual_site_failures_are_visible_partial_results(self):
        reports, manifest = self.reports(failed=8)
        result = summarize_scheduled.evaluate(reports, manifest)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['failed'], 8)
        self.assertEqual(len(result['failures']), 8)
        self.assertIn('실패 8', summarize_scheduled.markdown(result))

    def test_zero_failures_are_success(self):
        self.assertEqual(summarize_scheduled.evaluate(*self.reports())['status'], 'success')

    def test_below_ninety_percent_still_fails(self):
        self.assertEqual(summarize_scheduled.evaluate(*self.reports(failed=11))['status'], 'failure')
        self.assertEqual(summarize_scheduled.evaluate(*self.reports(failed=10))['status'], 'partial')

    def test_database_errors_fail_even_with_good_coverage(self):
        self.assertEqual(summarize_scheduled.evaluate(*self.reports(failed=1, kind='infrastructure'))['status'], 'failure')

    def test_unclassified_failure_is_never_silenced(self):
        self.assertEqual(summarize_scheduled.evaluate(*self.reports(failed=1, kind=None))['status'], 'failure')

    def test_missing_shard_duplicate_cafe_and_inconsistent_counts_fail(self):
        for change in ('missing', 'duplicate', 'counts'):
            reports, manifest = self.reports()
            if change == 'missing':
                reports.pop()
            elif change == 'duplicate':
                reports[0]['results'][0] = reports[0]['results'][1].copy()
            else:
                reports[0]['published'] = 0
            self.assertEqual(summarize_scheduled.evaluate(reports, manifest)['status'], 'failure', change)

    def test_empty_manifest_fails(self):
        self.assertEqual(summarize_scheduled.evaluate([], [])['status'], 'failure')

    def test_site_and_storage_errors_are_separated_without_raw_exceptions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'check.json'
            self.assertEqual(refresh_scheduled.failure_details(path)['failure_kind'], 'infrastructure')
            path.write_text(json.dumps({'error': 'storage: ConnectionError secret-url'}))
            details = refresh_scheduled.failure_details(path)
            self.assertEqual(details['failure_kind'], 'infrastructure')
            self.assertNotIn('secret-url', str(details))
            path.write_text(json.dumps({'http_calls': [{'status': 403}]}))
            self.assertEqual(refresh_scheduled.failure_details(path), {'failure_kind': 'site', 'reason': 'HTTP 403'})

    def run_refresh(self, check, allow=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'data/scheduled-crawlers.json').write_text(json.dumps([{'script': 'sync_example_db', 'cafe_id': '1'}]))
            report = root / 'reports/crawlers/supabase/sync_example_db-1.json'
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({'status': 'smoke_pass'}))

            def subprocess_run(*args, **kwargs):
                self.assertFalse(report.exists(), 'previous-run report must be removed before starting')
                if check is not None:
                    report.write_text(json.dumps(check))
                return SimpleNamespace(returncode=1)

            argv = ['refresh_scheduled.py'] + (['--allow-site-failures'] if allow else [])
            with patch.object(refresh_scheduled, 'ROOT', root), patch('sys.argv', argv), patch.object(refresh_scheduled.subprocess, 'run', side_effect=subprocess_run), contextlib.redirect_stdout(io.StringIO()):
                code = refresh_scheduled.main()
            result = json.loads((root / 'reports/scheduled/shard-0.json').read_text())
            return code, result

    def test_scheduled_mode_keeps_site_failure_in_report_but_manual_mode_fails(self):
        check = {'http_calls': [{'status': 403}]}
        self.assertEqual(self.run_refresh(check, allow=False)[0], 1)
        code, result = self.run_refresh(check, allow=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['published'], 0)
        self.assertEqual(result['results'][0]['status'], 'failed')
        self.assertEqual(result['results'][0]['failure_kind'], 'site')

    def test_scheduled_mode_never_hides_storage_errors_or_missing_reports(self):
        self.assertEqual(self.run_refresh({'error': 'storage: ConnectionError'}, allow=True)[0], 1)
        self.assertEqual(self.run_refresh({'error': 'ModuleNotFoundError: missing dependency'}, allow=True)[0], 1)
        self.assertEqual(self.run_refresh({'error': 'NameError: coding bug'}, allow=True)[0], 1)
        self.assertEqual(self.run_refresh(None, allow=True)[0], 1)


if __name__ == '__main__':
    unittest.main()
