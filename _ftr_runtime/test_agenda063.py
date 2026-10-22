"""Regresiones reproducidas en 06.2. Ninguna prueba consulta una fuente real."""
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
from _ftr_runtime.config import current_slot, load, digest
from _ftr_tools import ejecutar as entry

ROOT = Path(__file__).resolve().parents[1]
def at(value):
    return datetime.fromisoformat(value + '-03:00')

def configuration():
    value = load(ROOT)
    value.update(anchor='2026-10-19', period=2026)
    value['drive'] = dict(days=1, time='17:00', enabled=True)
    value['cnrt'] = dict(days=5, time='22:00', enabled=True)
    return value

def previous(config):
    moment = at('2026-10-19T23:27:00')
    return {k: dict(read_utc=moment.isoformat(), status='success',
                   served_slot=current_slot(config, k, moment)) for k in ('drive', 'cnrt')}

class Agenda063Tests(unittest.TestCase):
    def setUp(self):
        self.c=configuration(); self.s=previous(self.c)
    def jobs(self, value):
        return agenda.select_jobs(self.c, self.c, self.s, 'scheduled', at(value))
    def test_real_past_hour_save_does_not_hide_today(self):
        self.s['drive']['schedule_effective_from_utc']='2026-10-20T23:27:52.189945+00:00'
        self.assertEqual(self.jobs('2026-10-20T20:35:00'), ['drive'])
    def test_past_hour_not_green_when_yesterday_data(self):
        self.s['drive']['schedule_effective_from_utc']=at('2026-10-20T20:27:00').isoformat()
        status=agenda.describe(self.c,self.s,at('2026-10-20T20:35:00'))['drive']
        self.assertTrue(status['pending']);self.assertEqual(status['status'],'overdue')
    def test_future_hour_does_not_recover_yesterday(self):
        old=copy.deepcopy(self.c);self.c['drive']['time']='21:00'
        agenda.activate_changed_schedules(old,self.c,self.s,at('2026-10-20T20:27:00'))
        self.assertEqual(self.jobs('2026-10-20T20:37:00'),[])
        self.assertEqual(self.jobs('2026-10-20T21:07:00'),['drive'])
    def test_changed_past_hour_recovers_across_midnight(self):
        self.s['drive']['schedule_effective_from_utc']=at('2026-10-20T20:27:00').isoformat()
        self.assertEqual(self.jobs('2026-10-21T00:07:00'),['drive'])
    def test_successful_manual_before_hour_does_not_delay(self):
        read=at('2026-10-20T16:45:00')
        self.s['drive'].update(read_utc=read.isoformat(),attempt_utc=read.isoformat(),served_slot=current_slot(self.c,'drive',read))
        self.assertEqual(self.jobs('2026-10-20T17:07:00'),['drive'])
    def test_failed_manual_still_has_retry_cooldown(self):
        self.s['drive'].update(status='error',attempt_utc=at('2026-10-20T16:45:00').isoformat())
        self.assertEqual(self.jobs('2026-10-20T17:07:00'),[])
        self.assertEqual(self.jobs('2026-10-20T17:52:00'),['drive'])
    def test_read_after_changed_slot_not_repeated(self):
        self.s['drive'].update(read_utc=at('2026-10-20T18:00:00').isoformat(),served_slot='huella-anterior',schedule_effective_from_utc=at('2026-10-20T20:27:00').isoformat())
        self.assertEqual(self.jobs('2026-10-20T20:37:00'),[])
        self.assertFalse(agenda.describe(self.c,self.s,at('2026-10-20T20:37:00'))['drive']['pending'])
    def test_read_before_new_future_slot_does_not_satisfy_it(self):
        self.s['drive']['read_utc']=at('2026-10-20T18:00:00').isoformat()
        old=copy.deepcopy(self.c);self.c['drive']['time']='19:00'
        agenda.activate_changed_schedules(old,self.c,self.s,at('2026-10-20T18:30:00'))
        self.assertEqual(self.jobs('2026-10-20T19:07:00'),['drive'])
    def test_cnrt_past_hour_on_its_due_day_not_lost_five_days(self):
        old=copy.deepcopy(self.c);self.c['cnrt']['time']='20:00'
        agenda.activate_changed_schedules(old,self.c,self.s,at('2026-10-24T23:30:00'))
        self.assertIn('cnrt',self.jobs('2026-10-24T23:37:00'))
    def test_cnrt_off_cycle_not_requested(self):
        self.assertNotIn('cnrt',self.jobs('2026-10-20T23:37:00'))
    def test_no_sources_called_by_scheduler_functions(self):
        with patch.object(worker,'google_snapshot',side_effect=AssertionError),patch.object(worker,'cnrt_snapshot',side_effect=AssertionError):
            self.assertEqual(self.jobs('2026-10-20T20:37:00'),['drive'])
    def test_decision_does_not_change_last_read(self):
        before=copy.deepcopy(self.s);self.jobs('2026-10-20T20:37:00');self.assertEqual(before,self.s)
    def test_disabled_stays_disabled(self):
        self.c['drive']['enabled']=False;self.assertEqual(self.jobs('2026-10-20T20:37:00'),[])

class Coordinator063Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.c=configuration();self.c['lines']=[dict(line=2,company=2058,enabled=True)]
        self.s=previous(self.c)
        (self.root/'_ftr_config.json').write_text(json.dumps(self.c))
        (self.root/'_ftr_estado.json').write_text(json.dumps(self.s))
        for name in ('parques','controlados'):
            (self.root/name).mkdir();(self.root/name/'linea2.csv').write_text('dominio\nABC123\n')
    def tearDown(self):
        self.tmp.cleanup()
    def context(self,env,now):
        stack=ExitStack();stack.enter_context(patch.dict(os.environ,{'GITHUB_REF':'refs/heads/main','GITHUB_REPOSITORY':'SanLean17/parque-movil-ftr',**env},clear=True))
        stack.enter_context(patch.object(worker,'ROOT',self.root))
        stack.enter_context(patch.object(worker,'REPORT_DIR',self.root/'reports'))
        stack.enter_context(patch.object(worker,'now',return_value=now))
        for name in ('plan','selected','commit'):stack.enter_context(patch.object(worker,name,getattr(worker,name)))
        self.commit=stack.enter_context(patch.object(entry,'commit_validated',return_value='test-revision'))
        self.pages=stack.enter_context(patch.object(worker,'build_pages'))
        stack.enter_context(patch.object(worker,'update_public'))
        return stack
    def mock_source(self,key,read):
        def read_mock(root,config):
            name,stamp=('parques','ultima_actualizacion_parque.txt') if key=='cnrt' else ('controlados','ultima_actualizacion_controlados.txt')
            (root/name/'linea2.csv').write_text('dominio\nABC123\n')
            (root/stamp).write_text(read.isoformat())
            if key=='drive':(root/'estadisticas_ftr.json').write_text('{"fixture_agenda":true}')
            return dict(read_utc=read.isoformat(),completed_utc=at('2026-10-24T22:07:00').isoformat())
        return read_mock
    def test_plan_outputs_selected_sources_without_reading(self):
        env=dict(FTR_ACTION='scheduled',FTR_PHASE='check',GITHUB_OUTPUT=str(self.root/'outputs'))
        with self.context(env,at('2026-10-20T17:07:00')),patch.object(worker,'google_snapshot') as g,patch.object(worker,'cnrt_snapshot') as c:
            self.assertEqual(entry.main(),0);g.assert_not_called();c.assert_not_called()
        self.assertIn('sources=drive', (self.root/'outputs').read_text())
    def test_no_unprepared_cnrt_added_when_time_passes_during_setup(self):
        env=dict(FTR_ACTION='scheduled',FTR_PLANNED_SOURCES='drive')
        with self.context(env,at('2026-10-24T22:07:00')),patch.object(worker,'google_snapshot',side_effect=self.mock_source('drive',at('2026-10-24T22:07:00'))),patch.object(worker,'cnrt_snapshot',side_effect=AssertionError('CNRT no preparado')) as cnrt:
            self.assertEqual(entry.main(),0);cnrt.assert_not_called()
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertEqual(state['cnrt'],self.s['cnrt'])
    def test_read_start_not_finish_marks_served_slot(self):
        env=dict(FTR_ACTION='cnrt',FTR_PLANNED_SOURCES='cnrt')
        read=at('2026-10-24T21:58:00')
        with self.context(env,at('2026-10-24T22:07:00')),patch.object(worker,'cnrt_snapshot',side_effect=self.mock_source('cnrt',read)):
            self.assertEqual(entry.main(),0)
        state=json.loads((self.root/'_ftr_estado.json').read_text())
        self.assertEqual(state['cnrt']['served_slot'],current_slot(self.c,'cnrt',read))
        self.assertIn('cnrt',agenda.select_jobs(self.c,self.c,state,'scheduled',at('2026-10-24T22:22:00')))
    def test_invalid_prepared_plan_rejected_before_source(self):
        with self.context(dict(FTR_ACTION='scheduled',FTR_PLANNED_SOURCES='drive,unknown'),at('2026-10-20T17:07:00')),patch.object(worker,'google_snapshot') as source:
            self.assertEqual(entry.main(),1);source.assert_not_called();self.commit.assert_not_called()
    def test_schedule_save_does_not_read_or_mark_source(self):
        c=copy.deepcopy(self.c);c['drive']['time']='16:30'
        env=dict(FTR_ACTION='config',FTR_SCHEDULE_TOKEN='UNIT_TEST_NOT_A_REAL_CREDENTIAL',FTR_CONFIG=json.dumps(c),FTR_EXPECTED=digest(self.c),FTR_PLANNED_SOURCES='')
        with self.context(env,at('2026-10-20T20:27:00')),patch.object(worker,'google_snapshot') as source:
            self.assertEqual(entry.main(),0);source.assert_not_called()
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertEqual(state['drive']['read_utc'],self.s['drive']['read_utc'])
        self.assertEqual(agenda.select_jobs(c,c,state,'scheduled',at('2026-10-20T20:37:00')),['drive'])

if __name__=='__main__':unittest.main()
