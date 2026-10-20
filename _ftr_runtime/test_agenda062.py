import copy
import unittest
from datetime import datetime, timezone
from pathlib import Path
from _ftr_runtime import agenda
from _ftr_runtime.config import load, current_slot

ROOT=Path(__file__).resolve().parents[1]
def t(s):return datetime.fromisoformat(s+'-03:00')

class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.c=load(ROOT)
        self.state={k: {'served_slot':current_slot(self.c,k,t('2026-10-19T23:27:00')),
                        'read_utc': '2026-10-20T02:27:00+00:00', 'status':'success'} for k in ('drive','cnrt')}
    def jobs(self,when):return agenda.select_jobs(self.c,self.c,self.state,'scheduled',t(when))
    def test_before_due(self):self.assertEqual(self.jobs('2026-10-20T16:59:00'),[])
    def test_at_due(self):self.assertEqual(self.jobs('2026-10-20T17:00:00'),['drive'])
    def test_delayed_start_still_pending(self):self.assertEqual(self.jobs('2026-10-20T19:45:00'),['drive'])
    def test_after_midnight_recovers_latest_turn(self):self.assertEqual(self.jobs('2026-10-21T02:00:00'),['drive'])
    def test_existing_success_not_green_when_late(self):
        s=agenda.describe(self.c,self.state,t('2026-10-20T18:30:00'))
        self.assertEqual(s['drive']['status'],'overdue');self.assertEqual(s['drive']['overdue_minutes'],90)
        self.assertEqual(s['cnrt']['status'],'saved')
    def test_pending_first_thirty_minutes(self):
        self.assertEqual(agenda.describe(self.c,self.state,t('2026-10-20T17:07:00'))['drive']['status'],'pending')
    def test_served_not_repeated(self):
        self.state['drive']['served_slot']=current_slot(self.c,'drive',t('2026-10-20T19:00:00'))
        self.assertEqual(self.jobs('2026-10-20T19:45:00'),[])
    def test_new_hour_waits_until_today_nineteen(self):
        old=copy.deepcopy(self.c);self.c['drive']['time']='19:00'
        agenda.activate_changed_schedules(old,self.c,self.state,t('2026-10-20T18:00:00'))
        self.assertEqual(self.jobs('2026-10-20T18:07:00'),[])
        self.assertEqual(self.jobs('2026-10-20T18:59:59'),[])
        self.assertEqual(self.jobs('2026-10-20T19:00:00'),['drive'])
        self.assertEqual(self.jobs('2026-10-20T19:37:00'),['drive'])
    def test_save_never_fakes_read_or_served(self):
        old=copy.deepcopy(self.c);before=copy.deepcopy(self.state);self.c['drive']['time']='19:00'
        agenda.activate_changed_schedules(old,self.c,self.state,t('2026-10-20T18:00:00'))
        self.assertEqual(self.state['drive']['read_utc'],before['drive']['read_utc'])
        self.assertEqual(self.state['drive']['served_slot'],before['drive']['served_slot'])
        self.assertEqual(self.state['cnrt'],before['cnrt'])
    def test_frequency_schedule_change_future_only(self):
        old=copy.deepcopy(self.c);self.c['cnrt']['days']=1
        agenda.activate_changed_schedules(old,self.c,self.state,t('2026-10-20T18:00:00'))
        self.assertNotIn('cnrt',self.jobs('2026-10-20T21:59:00'))
        self.assertIn('cnrt',self.jobs('2026-10-20T22:00:00'))
    def test_no_change_does_not_reset_due(self):
        before=copy.deepcopy(self.state)
        agenda.activate_changed_schedules(self.c,self.c,self.state,t('2026-10-20T18:00:00'))
        self.assertEqual(self.state,before);self.assertEqual(self.jobs('2026-10-20T18:07:00'),['drive'])
    def test_schedule_save_selects_no_sources(self):
        new=copy.deepcopy(self.c);new['drive']['time']='19:00'
        self.assertEqual(agenda.select_jobs(new,self.c,self.state,'config',t('2026-10-20T18:00:00')),[])
    def test_source_change_preserves_validation(self):
        new=copy.deepcopy(self.c);new['period']=2027
        self.assertEqual(agenda.select_jobs(new,self.c,self.state,'config',t('2026-10-20T18:00:00')),['drive'])
    def test_manual_operations_unchanged(self):
        for mode,want in [('drive',['drive']),('cnrt',['cnrt']),('all',['cnrt','drive'])]:
            self.assertEqual(agenda.select_jobs(self.c,self.c,self.state,mode,t('2026-10-20T16:00:00')),want)
    def test_retry_keeps_pending_but_not_eligible(self):
        self.state['drive'].update(attempt_utc=t('2026-10-20T17:10:00').isoformat(),status='error')
        s=agenda.describe(self.c,self.state,t('2026-10-20T17:20:00'))['drive']
        self.assertTrue(s['pending']);self.assertFalse(s['eligible']);self.assertEqual(s['status'],'error')
    def test_disabled(self):
        self.c['drive']['enabled']=False
        s=agenda.describe(self.c,self.state,t('2026-10-20T20:00:00'))['drive']
        self.assertEqual(s['status'],'disabled');self.assertIsNone(s['next_due_utc'])
    def test_explanation_without_sources_or_secrets(self):
        text=agenda.explain(self.c,self.state,t('2026-10-20T16:34:00'),[],'scheduled')
        self.assertIn('NO significa actualizar',text);self.assertNotIn(self.c['sheetUrl'],text)
    def test_describe_does_not_mutate(self):
        before=copy.deepcopy(self.state);agenda.describe(self.c,self.state,t('2026-10-20T18:00:00'))
        self.assertEqual(before,self.state)

if __name__=='__main__':unittest.main()
