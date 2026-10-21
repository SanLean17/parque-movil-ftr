"""Pruebas aisladas: reloj, Google, CNRT, Git y Pages simulados; sin credenciales."""
import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from _ftr_runtime import agenda, worker
from _ftr_runtime.config import current_slot, digest
from _ftr_tools import ejecutar as entry


def at(value):
    return datetime.fromisoformat(value + '-03:00')


def configuration():
    return dict(version=2, period=2026,
                sheetUrl='https://docs.google.com/spreadsheets/d/UNIT_TEST_ONLY_1234567890123456789/edit',
                timezone='America/Argentina/Buenos_Aires', anchor='2026-10-19',
                drive=dict(days=1, time='17:00', enabled=True),
                cnrt=dict(days=5, time='22:00', enabled=True),
                lines=[dict(line=2, company=2058, enabled=True)])


class ScheduleReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.c = configuration()
        self.s = {}
        for key, stamp in [('drive', '2026-10-20T23:47:00'), ('cnrt', '2026-10-19T22:38:00')]:
            read = at(stamp)
            self.s[key] = dict(status='success', read_utc=read.isoformat(),
                               served_slot=current_slot(self.c, key, read))
        self.s['drive']['schedule_effective_from_utc'] = at('2026-10-21T01:18:00').isoformat()
        self.write_config()
        (self.root/'_ftr_estado.json').write_text(json.dumps(self.s), encoding='utf-8')
        for folder in ('controlados', 'parques'):
            (self.root/folder).mkdir()
            (self.root/folder/'linea2.csv').write_text('dominio\nABC123\n', encoding='utf-8')
        (self.root/'event.json').write_text(json.dumps({'schedule': '0 3 * * *'}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self):
        (self.root/'_ftr_config.json').write_text(json.dumps(self.c), encoding='utf-8')

    def source(self, key, moment):
        def produce(root, config):
            folder, stamp = ('controlados', 'ultima_actualizacion_controlados.txt') if key == 'drive' else ('parques', 'ultima_actualizacion_parque.txt')
            (root/folder/'linea2.csv').write_text('linea,fecha,dominio,interno\n2,21/10/2026,ABC123,1\n', encoding='utf-8')
            (root/stamp).write_text(moment.isoformat(), encoding='utf-8')
            return dict(read_utc=moment.isoformat(), completed_utc=moment.isoformat())
        return produce

    def context(self, moment, **env):
        stack = ExitStack()
        stack.enter_context(patch.dict(os.environ, {
            'FTR_ACTION': 'scheduled', 'GITHUB_EVENT_NAME': 'schedule',
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_REPOSITORY': 'SanLean17/parque-movil-ftr',
            'GITHUB_EVENT_PATH': str(self.root/'event.json'), **env}, clear=True))
        stack.enter_context(patch.object(worker, 'ROOT', self.root))
        stack.enter_context(patch.object(worker, 'REPORT_DIR', self.root/'report'))
        stack.enter_context(patch.object(worker, 'now', return_value=moment))
        for name in ('plan', 'selected', 'commit'):
            stack.enter_context(patch.object(worker, name, getattr(worker, name)))
        self.google = stack.enter_context(patch.object(worker, 'google_snapshot', side_effect=self.source('drive', moment)))
        self.cnrt = stack.enter_context(patch.object(worker, 'cnrt_snapshot', side_effect=self.source('cnrt', moment)))
        self.commit = stack.enter_context(patch.object(entry, 'commit_validated', return_value='TEST_ONLY_REVISION'))
        self.pages = stack.enter_context(patch.object(worker, 'build_pages'))
        stack.enter_context(patch.object(worker, 'update_public'))
        stack.enter_context(patch.object(entry.native_schedule, 'preflight'))
        return stack

    def test_actual_0512_case_plans_drive_without_reading_during_check(self):
        when = at('2026-10-21T05:12:00')
        self.assertEqual(agenda.select_jobs(self.c, self.c, self.s, 'scheduled', when), [])
        before = (self.root/'_ftr_estado.json').read_bytes()
        with self.context(when, FTR_PHASE='check', GITHUB_OUTPUT=str(self.root/'out'), GITHUB_STEP_SUMMARY=str(self.root/'summary')):
            self.assertEqual(entry.main(), 0)
            self.google.assert_not_called()
            self.cnrt.assert_not_called()
            self.commit.assert_not_called()
        self.assertIn('work=true', (self.root/'out').read_text())
        self.assertIn('sources=drive', (self.root/'out').read_text())
        self.assertIn('0 3 * * *', (self.root/'summary').read_text())
        self.assertEqual(before, (self.root/'_ftr_estado.json').read_bytes())

    def test_extra_0512_execution_reads_and_publishes_drive_not_cnrt(self):
        with self.context(at('2026-10-21T05:12:00'), FTR_PLANNED_SOURCES='drive'):
            self.assertEqual(entry.main(), 0)
            self.google.assert_called_once()
            self.cnrt.assert_not_called()
            self.assertEqual(self.commit.call_count,2)  # Datos y recibo separado de publicación verificada.
            self.pages.assert_called_once()
        state = json.loads((self.root/'_ftr_estado.json').read_text())
        self.assertEqual(state['cnrt'], self.s['cnrt'])
        self.assertEqual(state['drive']['read_utc'], at('2026-10-21T05:12:00').isoformat())

    def test_extra_read_does_not_cancel_1700_read(self):
        for stamp in ('2026-10-21T05:12:00', '2026-10-21T17:00:00'):
            with self.context(at(stamp), FTR_PLANNED_SOURCES='drive'):
                self.assertEqual(entry.main(), 0)
                self.google.assert_called_once()
                self.cnrt.assert_not_called()
        state = json.loads((self.root/'_ftr_estado.json').read_text())
        self.assertEqual(state['drive']['read_utc'], at('2026-10-21T17:00:00').isoformat())

    def test_even_already_satisfied_turn_reads_on_new_calendar_arrival(self):
        when = at('2026-10-21T17:30:00')
        self.s['drive'].update(read_utc=at('2026-10-21T17:10:00').isoformat(), served_slot=current_slot(self.c, 'drive', when))
        (self.root/'_ftr_estado.json').write_text(json.dumps(self.s))
        with self.context(when, FTR_PLANNED_SOURCES='drive'):
            self.assertEqual(entry.main(), 0)
            self.google.assert_called_once()

    def test_cnrt_due_day_processes_both(self):
        with self.context(at('2026-10-24T22:00:00'), FTR_PLANNED_SOURCES='cnrt,drive'):
            self.assertEqual(entry.main(), 0)
            self.cnrt.assert_called_once()
            self.google.assert_called_once()

    def test_paused_drive_is_not_forced(self):
        self.c['drive']['enabled'] = False
        self.write_config()
        with self.context(at('2026-10-21T05:12:00')):
            self.assertEqual(entry.main(), 0)
            self.google.assert_not_called()
            self.cnrt.assert_not_called()
            self.commit.assert_not_called()

    def test_manual_cnrt_remains_only_cnrt(self):
        with self.context(at('2026-10-21T05:12:00'), FTR_ACTION='cnrt', GITHUB_EVENT_NAME='workflow_dispatch', FTR_PLANNED_SOURCES='cnrt'):
            self.assertEqual(entry.main(), 0)
            self.google.assert_not_called()
            self.cnrt.assert_called_once()

    def test_saving_schedule_does_not_trigger_extra_read(self):
        candidate = copy.deepcopy(self.c)
        candidate['drive']['time'] = '18:00'
        with self.context(at('2026-10-21T05:12:00'), FTR_ACTION='config', GITHUB_EVENT_NAME='workflow_dispatch',
                          FTR_CONFIG=json.dumps(candidate), FTR_EXPECTED=digest(self.c), FTR_PLANNED_SOURCES=''):
            self.assertEqual(entry.main(), 0)
            self.google.assert_not_called()
            self.cnrt.assert_not_called()
        state = json.loads((self.root/'_ftr_estado.json').read_text())
        self.assertEqual(state['drive']['read_utc'], self.s['drive']['read_utc'])

    def test_passive_panel_agenda_does_not_create_immediate_pending(self):
        before = copy.deepcopy(self.s)
        state = agenda.describe(self.c, self.s, at('2026-10-21T05:12:00'))
        self.assertFalse(state['drive']['pending'])
        self.assertEqual(state['drive']['next_due_utc'], '2026-10-21T20:00:00+00:00')
        self.assertEqual(self.s, before)

    def test_validation_failure_preserves_controls_and_last_read(self):
        before = (self.root/'controlados/linea2.csv').read_bytes()
        with self.context(at('2026-10-21T05:12:00'), FTR_PLANNED_SOURCES='drive'):
            self.google.side_effect = ValueError('Datos ficticios inválidos')
            self.assertEqual(entry.main(), 1)
            self.google.assert_called_once()
        self.assertEqual(before, (self.root/'controlados/linea2.csv').read_bytes())
        state = json.loads((self.root/'_ftr_estado.json').read_text())
        self.assertEqual(state['drive']['read_utc'], self.s['drive']['read_utc'])
        self.assertEqual(state['drive']['status'], 'error')

    def test_no_unprepared_cnrt_added_to_extra_read(self):
        with self.context(at('2026-10-24T22:01:00'), FTR_PLANNED_SOURCES='drive'):
            self.assertEqual(entry.main(), 0)
            self.google.assert_called_once()
            self.cnrt.assert_not_called()

    def test_non_schedule_events_do_not_enable_extra_read(self):
        for event in ('workflow_dispatch', 'push', 'pull_request', ''):
            self.assertEqual(entry.sources_for_execution('scheduled', self.c, [], event), [])
        for mode in ('config', 'cnrt', 'drive', 'all', 'diagnostic'):
            self.assertEqual(entry.sources_for_execution(mode, self.c, [], 'schedule'), [])

    def test_extra_read_respects_one_hour_after_error(self):
        state = {'drive':{'status':'error','attempt_utc':at('2026-10-21T16:55:00').isoformat()}}
        self.assertEqual(entry.sources_for_execution('scheduled',self.c,[],'schedule',state,at('2026-10-21T17:00:00')),[])
        self.assertEqual(entry.sources_for_execution('scheduled',self.c,[],'schedule',state,at('2026-10-21T17:55:00')),['drive'])

    def test_source_order_and_no_duplicate_drive(self):
        jobs = ['cnrt', 'drive']
        self.assertEqual(entry.sources_for_execution('scheduled', self.c, jobs, 'schedule'), jobs)
        self.assertEqual(entry.sources_for_execution('scheduled', self.c, ['cnrt'], 'schedule'), jobs)
        self.assertEqual(jobs, ['cnrt', 'drive'])

    def test_cron_origin_never_dumps_unrelated_event_fields(self):
        (self.root/'event.json').write_text(json.dumps({'schedule': '0 20 * * *', 'private': 'DO_NOT_LOG'}))
        with self.context(at('2026-10-21T05:12:00')):
            self.assertEqual(entry.cron_origin(), '0 20 * * *')
        (self.root/'event.json').write_text(json.dumps({'schedule': '::warning::NOT_ALLOWED'}))
        with self.context(at('2026-10-21T05:12:00')):
            self.assertIsNone(entry.cron_origin())

    def test_cron_origin_missing_and_malformed_do_not_stop_read(self):
        for text in ('not json', '[]', '{"schedule": 123}'):
            (self.root/'event.json').write_text(text)
            with self.context(at('2026-10-21T05:12:00')):
                self.assertIsNone(entry.cron_origin())
        with self.context(at('2026-10-21T05:12:00'), GITHUB_EVENT_PATH=''):
            self.assertIsNone(entry.cron_origin())


if __name__ == '__main__':
    unittest.main()
