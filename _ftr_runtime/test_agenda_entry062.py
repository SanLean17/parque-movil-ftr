import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from _ftr_runtime.config import load, digest, current_slot
from _ftr_runtime import worker, agenda
from _ftr_tools import ejecutar as entry

ROOT=Path(__file__).resolve().parents[1]
def moment(s):return datetime.fromisoformat(s+'-03:00')

class EntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=load(ROOT)
        self.state={k:{'read_utc':'2026-10-20T02:27:00+00:00','status':'success','served_slot':current_slot(self.config,k,moment('2026-10-19T23:27:00'))} for k in ('drive','cnrt')}
        (self.root/'_ftr_config.json').write_text(json.dumps(self.config))
        (self.root/'_ftr_estado.json').write_text(json.dumps(self.state))
        for n in ('parques','controlados'):(self.root/n).mkdir()
    def tearDown(self):self.tmp.cleanup()
    def context(self,env,when):
        s=ExitStack()
        s.enter_context(patch.dict(os.environ,env,clear=True))
        s.enter_context(patch.object(worker,'ROOT',self.root))
        s.enter_context(patch.object(worker,'now',return_value=moment(when)))
        for name in ('plan','selected','commit'):s.enter_context(patch.object(worker,name,getattr(worker,name)))
        self.google=s.enter_context(patch.object(worker,'google_snapshot',side_effect=AssertionError('Google no permitido')))
        self.cnrt=s.enter_context(patch.object(worker,'cnrt_snapshot',side_effect=AssertionError('CNRT no permitido')))
        self.commit=s.enter_context(patch.object(entry,'commit_validated',return_value='test-sha'))
        self.pages=s.enter_context(patch.object(worker,'build_pages'))
        s.enter_context(patch.object(worker,'update_public'))
        return s
    def test_scheduled_check_after_hour_only_outputs_plan(self):
        env={'FTR_ACTION':'scheduled','FTR_PHASE':'check','GITHUB_OUTPUT':str(self.root/'out'),'GITHUB_STEP_SUMMARY':str(self.root/'summary')}
        before=(self.root/'_ftr_estado.json').read_bytes()
        with self.context(env,'2026-10-20T19:07:00'):
            self.assertEqual(entry.main(),0)
            self.google.assert_not_called();self.cnrt.assert_not_called();self.commit.assert_not_called()
        self.assertIn('work=true',(self.root/'out').read_text())
        self.assertIn('cnrt=false',(self.root/'out').read_text())
        self.assertEqual((self.root/'_ftr_estado.json').read_bytes(),before)
    def test_saving_only_hour_does_not_fetch(self):
        c=copy.deepcopy(self.config);c['drive']['time']='19:00'
        env={'FTR_ACTION':'config','FTR_CONFIG':json.dumps(c),'FTR_EXPECTED':digest(self.config),
             'GITHUB_REF':'refs/heads/main','GITHUB_REPOSITORY':'SanLean17/parque-movil-ftr'}
        with self.context(env,'2026-10-20T18:20:00'):
            self.assertEqual(entry.main(),0)
            self.google.assert_not_called();self.cnrt.assert_not_called()
        after=json.loads((self.root/'_ftr_estado.json').read_text())
        self.assertEqual(after['drive']['read_utc'],self.state['drive']['read_utc'])
        self.assertEqual(after['drive']['served_slot'],self.state['drive']['served_slot'])
        self.assertIn('schedule_effective_from_utc',after['drive'])
        self.assertEqual(agenda.select_jobs(c,c,after,'scheduled',moment('2026-10-20T18:37:00')),[])
        self.assertEqual(agenda.select_jobs(c,c,after,'scheduled',moment('2026-10-20T19:07:00')),['drive'])

if __name__=='__main__':unittest.main()
