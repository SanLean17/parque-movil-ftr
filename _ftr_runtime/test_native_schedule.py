"""Pruebas de cron/configuración; no usan Google, CNRT ni credenciales reales."""
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from _ftr_runtime import native_schedule as native
from _ftr_runtime.config import load, encoded, digest
from _ftr_runtime import worker
from _ftr_tools import ejecutar as entry

ROOT = Path(__file__).resolve().parents[1]
FAKE = 'UNIT_TEST_NOT_A_REAL_CREDENTIAL'


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = load(ROOT)
        self.config['drive']['time'] = '17:00'
        self.config['cnrt']['time'] = '22:00'
        (self.root / native.PATH).parent.mkdir(parents=True)
        (self.root / native.PATH).write_text(native.render(self.config), encoding='utf-8')
        (self.root / '_ftr_config.json').write_bytes(encoded(self.config))

    def tearDown(self):
        self.tmp.cleanup()

    def parsed(self, c=None):
        return yaml.load(native.render(c or self.config), Loader=yaml.BaseLoader)

    def crons(self, c=None):
        return [r['cron'] for r in self.parsed(c)['on'].get('schedule', [])]

    def test_17_local_is_20_utc(self):
        self.assertIn('0 20 * * *', self.crons())

    def test_22_local_is_01_utc(self):
        self.assertIn('0 1 * * *', self.crons())

    def test_arbitrary_minutes_preserved(self):
        self.config['drive']['time'] = '17:23'
        self.assertIn('23 20 * * *', self.crons())

    def test_midnight_catchup_not_duplicated(self):
        self.config['drive']['time'] = '00:00'
        self.assertEqual(self.crons().count('0 3 * * *'), 1)

    def test_both_same_hour_one_trigger(self):
        self.config['drive']['time'] = '22:00'
        self.assertEqual(self.crons(), ['0 1 * * *', '0 3 * * *'])

    def test_all_twentyfour_hours(self):
        for h in range(24):
            with self.subTest(hour=h):
                self.config['drive']['time'] = f'{h:02d}:35'
                self.assertIn(f'35 {(h + 3) % 24} * * *', self.crons())

    def test_only_enabled_sources(self):
        self.config['drive']['enabled'] = False
        self.assertNotIn('0 20 * * *', self.crons())

    def test_both_paused_no_schedule_but_manual_kept(self):
        self.config['drive']['enabled'] = False
        self.config['cnrt']['enabled'] = False
        self.assertNotIn('schedule', self.parsed()['on'])
        self.assertIn('workflow_dispatch', self.parsed()['on'])

    def test_no_every_five_days_day_of_month_bug(self):
        self.config['cnrt']['days'] = 5
        for expression in self.crons():
            self.assertEqual(expression.split()[2:], ['*', '*', '*'])
        self.assertIn('cada 5 día(s)', native.render(self.config))

    def test_no_secrets_or_sheet_url_in_calendar(self):
        text = native.render(self.config)
        self.assertNotIn(self.config['sheetUrl'], text)
        self.assertNotIn(FAKE, text)

    def test_only_one_reusable_coordinator(self):
        p = self.parsed()
        self.assertNotIn('concurrency', p)
        self.assertNotIn('push', p['on'])
        self.assertEqual(p['jobs']['actualizar']['uses'], './.github/workflows/ftr_sincronizar.yml')
        self.assertIn("'scheduled'", p['jobs']['actualizar']['with']['action'])

    def test_injection_rejected(self):
        self.config['drive']['time'] = '17:00\n jobs: malicious'
        with self.assertRaises(ValueError):
            native.render(self.config)

    def test_unchanged_does_not_require_extra_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            native.preflight(self.root, self.config)
            self.assertFalse(native.stage(self.root, self.config))

    def test_missing_secret_does_not_change_any_file(self):
        self.config['drive']['time'] = '19:00'
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'FTR_SCHEDULE_TOKEN'):
                native.stage(self.root, self.config)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_preflight_is_read_only(self):
        before = (self.root / native.PATH).read_bytes()
        self.config['drive']['time'] = '19:00'
        with patch.dict(os.environ, {native.TOKEN_NAME: FAKE}, clear=True):
            native.preflight(self.root, self.config)
        self.assertEqual(before, (self.root / native.PATH).read_bytes())

    def test_stage_changes_only_the_workflow(self):
        before = (self.root / '_ftr_config.json').read_bytes()
        self.config['drive']['time'] = '19:00'
        with patch.dict(os.environ, {native.TOKEN_NAME: FAKE}, clear=True):
            self.assertTrue(native.stage(self.root, self.config))
        self.assertIn("'0 22 * * *'", (self.root / native.PATH).read_text(encoding='utf-8'))
        self.assertEqual(before, (self.root / '_ftr_config.json').read_bytes())

    def test_line_changes_do_not_require_workflow_edit(self):
        self.config['lines'].append(dict(line=36, company=1234, enabled=True))
        with patch.dict(os.environ, {}, clear=True):
            native.preflight(self.root, self.config)

    def test_period_link_do_not_change_native_calendar(self):
        self.config['period'] = 2027
        self.config['sheetUrl'] = 'https://docs.google.com/spreadsheets/d/' + 'a' * 30 + '/edit'
        self.assertFalse(native.changed(self.root, self.config))

    def test_push_never_exposes_token_in_argv_or_persists_it(self):
        response = subprocess.CompletedProcess([], 0, '', '')
        with patch.dict(os.environ, {native.TOKEN_NAME: FAKE}, clear=True), patch.object(native.subprocess, 'run', return_value=response) as run:
            native.push(self.root)
        args, kwargs = run.call_args
        self.assertNotIn(FAKE, repr(args))
        self.assertEqual(args[0][-3:], ['push', native.REPO_URL, 'HEAD:main'])
        self.assertNotIn('--force', args[0])
        self.assertIn('FTR_CALENDAR_GIT_AUTH', kwargs['env'])
        self.assertFalse((self.root / '.git').exists())

    def test_push_error_does_not_echo_secret_or_git_output(self):
        response = subprocess.CompletedProcess([], 1, FAKE, 'remote token=' + FAKE)
        with patch.dict(os.environ, {native.TOKEN_NAME: FAKE}, clear=True), patch.object(native.subprocess, 'run', return_value=response):
            with self.assertRaises(ValueError) as err:
                native.push(self.root)
        self.assertNotIn(FAKE, str(err.exception))
        self.assertIn('Contents y Workflows', str(err.exception))

    def test_timeout_is_not_claimed_as_success(self):
        with patch.dict(os.environ, {native.TOKEN_NAME: FAKE}, clear=True), patch.object(native.subprocess, 'run', side_effect=subprocess.TimeoutExpired('git', 120)):
            with self.assertRaisesRegex(ValueError, 'No se pudo confirmar'):
                native.push(self.root)

    def test_preflight_blocks_before_reading_sources(self):
        changed = copy.deepcopy(self.config)
        changed['drive']['time'] = '19:00'
        env = dict(FTR_ACTION='config', FTR_CONFIG=json.dumps(changed), FTR_EXPECTED=digest(self.config), FTR_PHASE='check')
        with patch.dict(os.environ, env, clear=True), patch.object(worker, 'ROOT', self.root), patch.object(worker, 'REPORT_DIR', self.root / 'report'), patch.object(worker, 'google_snapshot') as g, patch.object(worker, 'cnrt_snapshot') as c, patch.object(worker, 'plan', entry.audited_plan):
            self.assertEqual(worker.main(), 1)
            g.assert_not_called()
            c.assert_not_called()
        self.assertEqual(json.loads((self.root / '_ftr_config.json').read_text()), self.config)

    def test_config_and_calendar_committed_together(self):
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=self.root, text=True, encoding='utf-8', stderr=subprocess.PIPE).strip()
        git('init', '-b', 'main')
        git('config', 'user.name', 'Unit Test')
        git('config', 'user.email', 'unit@example.invalid')
        git('add', '.')
        git('commit', '-m', 'base')
        before = git('rev-parse', 'HEAD')
        changed = copy.deepcopy(self.config)
        changed['drive']['time'] = '19:00'
        (self.root / '_ftr_config.json').write_bytes(encoded(changed))
        seen = []
        def simulated_push(root):
            seen.append(set(git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines()))
            self.assertEqual(git('show', 'HEAD:' + native.PATH) + '\n', native.render(changed))
            self.assertEqual(json.loads(git('show', 'HEAD:_ftr_config.json')), changed)
        with patch.dict(os.environ, {'FTR_ACTION': 'config', native.TOKEN_NAME: FAKE, 'PATH': os.environ.get('PATH', ''), 'SYSTEMROOT': os.environ.get('SYSTEMROOT', '')}, clear=True), patch.object(native, 'push', side_effect=simulated_push):
            revision = entry.commit_validated(self.root, ['_ftr_config.json'])
        self.assertNotEqual(revision, before)
        self.assertEqual(seen, [{'_ftr_config.json', native.PATH}])


if __name__ == '__main__':
    unittest.main()
