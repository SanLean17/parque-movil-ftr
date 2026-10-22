"""Fechas, persistencia y ejecución completas con fuentes y Git ficticios."""
import copy
import json
import os
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import Mock,patch
from _ftr_runtime import oneoff,worker,agenda
from _ftr_runtime.config import load,digest,current_slot
from _ftr_tools import ejecutar

REPO=Path(__file__).resolve().parents[1]


class OneoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        self.clock=datetime(2026,10,21,20,45,tzinfo=timezone.utc)
        self.config=load(REPO);self.config['lines']=[dict(line=36,company=9999,enabled=True)]
        self.state={k:dict(status='success',read_utc='2026-10-21T20:00:00+00:00' if k=='drive' else '2026-10-20T01:00:00+00:00',served_slot=current_slot(self.config,k,self.clock)) for k in ('drive','cnrt')}
        for folder in ('parques','controlados'):
            (self.root/folder).mkdir();(self.root/folder/'linea36.csv').write_text('dominio,interno,linea\nAA111AA,1,36\n',encoding='utf-8')
        for file in ('index.html','linea.html','ftr-datos.js','ftr-publica.js','ftr-historial.js','ftr-historial-publico.js'):shutil.copy2(REPO/file,self.root/file)
        (self.root/'_ftr_config.json').write_text(json.dumps(self.config));(self.root/'_ftr_estado.json').write_text(json.dumps(self.state))
        (self.root/oneoff.FILE).write_text(json.dumps(oneoff.empty()))
        (self.root/oneoff.WORKFLOW).parent.mkdir(parents=True);(self.root/oneoff.WORKFLOW).write_text(oneoff.render(oneoff.empty()),encoding='utf-8')
        for name in ('ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt'):(self.root/name).write_text('2026-10-20T01:00:00+00:00\n')
        self.commits=[];self.reads=[];self.failing=set();self.counter=0
        self.auth=patch.object(oneoff.native_schedule,'authorization',return_value='FICTICIO_NO_CREDENCIAL');self.auth.start()
    def tearDown(self):self.auth.stop();self.temp.cleanup()
    def commit(self,root,paths):
        self.commits.append(dict(paths=list(paths),data=copy.deepcopy(oneoff.load(root)),reads=list(self.reads)));return 'REVISION_FICTICIA'
    def set(self,key='cnrt',day='2026-10-21',time='18:00',expected=None):
        self.counter+=1;identifier=f'{self.counter:032x}'
        oneoff.apply_command(self.root,'oneoff-set',dict(source=key,date=day,time=time,expected_id=expected),identifier,self.clock,self.commit)
        return identifier
    def read(self,key,root,config):
        self.reads.append(key)
        self.assertEqual(oneoff.load(self.root)['last_execution'][key]['status'],'running')
        self.assertEqual(self.commits[-1]['reads'],self.reads[:-1])
        started=self.clock.isoformat();self.clock+=timedelta(minutes=5)
        if key in self.failing:raise ValueError('Falla ficticia de la fuente')
        folder,stamp=('parques','ultima_actualizacion_parque.txt') if key=='cnrt' else ('controlados','ultima_actualizacion_controlados.txt')
        (root/folder/'linea36.csv').write_text('dominio,interno,linea\nBB222BB,1,36\n',encoding='utf-8')
        (root/stamp).write_text(started+'\n')
        if key=='drive':(root/'estadisticas_ftr.json').write_text('{"fixture_agenda":true}')
        return dict(read_utc=started,completed_utc=self.clock.isoformat(),period=2026)
    def execute(self,mode='oneoff',payload=None,identifier='',run='101'):
        with ExitStack() as s:
            env=dict(FTR_ACTION=mode,FTR_CONFIG=json.dumps(payload or {}),FTR_REQUEST_ID=identifier,FTR_EXPECTED=digest(self.config),GITHUB_REF='refs/heads/main',GITHUB_REPOSITORY='SanLean17/parque-movil-ftr',GITHUB_RUN_ID=run)
            s.enter_context(patch.dict(os.environ,env));s.enter_context(patch.object(worker,'ROOT',self.root));s.enter_context(patch.object(worker,'REPORT_DIR',Path(self.temp.name)/'report'))
            s.enter_context(patch.object(worker,'now',side_effect=lambda:self.clock));s.enter_context(patch.object(worker,'plan',ejecutar._original_plan));s.enter_context(patch.object(worker,'selected',agenda.select_jobs))
            s.enter_context(patch.object(worker,'commit',side_effect=self.commit));s.enter_context(patch.object(worker,'build_pages'))
            s.enter_context(patch.object(worker,'google_snapshot',side_effect=lambda r,c:self.read('drive',r,c)));s.enter_context(patch.object(worker,'cnrt_snapshot',side_effect=lambda r,c:self.read('cnrt',r,c)))
            return worker.main()
    def test_today_future_each_source_and_tomorrow_are_independent(self):
        self.set('drive');self.set('cnrt','2026-10-22','09:00')
        data=oneoff.load(self.root);self.assertEqual(set(data['pending']),{'drive','cnrt'})
        self.assertIn("'0 21 21 10 *'",oneoff.render(data));self.assertIn("'0 12 22 10 *'",oneoff.render(data))
    def test_past_yesterday_same_minute_and_invalid_dates_rejected(self):
        for day,time in [('2026-10-20','22:00'),('2026-10-21','17:30'),('2026-10-21','17:45'),('2026-02-30','18:00')]:
            with self.subTest(day=day,time=time),self.assertRaises(ValueError):self.set(day=day,time=time)
        self.assertFalse(oneoff.load(self.root)['pending'])
    def test_month_year_and_buenos_aires_rollover(self):
        for day,clock,cron in [('2026-10-31','23:30','30 2 1 11 *'),('2026-12-31','23:30','30 2 1 1 *')]:
            expected=oneoff.load(self.root)['pending'].get('cnrt',{}).get('id');self.set(day=day,time=clock,expected=expected)
            self.assertIn(cron,(self.root/oneoff.WORKFLOW).read_text())
    def test_change_cancel_only_pending_and_stale_change_rejected(self):
        protected={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p.name not in (oneoff.FILE,'ftr_extraordinarias.yml')}
        first=self.set();second=self.set(time='19:30',expected=first)
        with self.assertRaisesRegex(ValueError,'cambió'):self.set(time='20:30',expected=first)
        oneoff.apply_command(self.root,'oneoff-cancel',dict(source='cnrt',expected_id=second),'f'*32,self.clock,self.commit)
        self.assertFalse(oneoff.load(self.root)['pending']);self.assertNotIn('  schedule:',(self.root/oneoff.WORKFLOW).read_text())
        self.assertEqual({p:p.read_bytes() for p in protected},protected);self.assertEqual(self.reads,[])
    def test_once_only_and_normal_five_day_calendar_unchanged(self):
        self.set();before=agenda.describe(self.config,self.state,self.clock)['cnrt']['next_due_utc'];self.clock+=timedelta(minutes=15)
        self.assertEqual(self.execute(),0);self.assertEqual(self.reads,['cnrt'])
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertEqual(agenda.describe(self.config,state,self.clock)['cnrt']['next_due_utc'],before)
        self.assertEqual(self.config['cnrt']['days'],5);self.assertFalse(oneoff.load(self.root)['pending'])
        self.assertEqual(self.execute(run='102'),0);self.clock+=timedelta(days=1);self.assertEqual(self.execute(run='103'),0);self.assertEqual(self.reads,['cnrt'])
    def test_drive_only_and_daily_calendar_unchanged(self):
        self.set('drive');before=agenda.describe(self.config,self.state,self.clock)['drive']['next_due_utc'];self.clock+=timedelta(minutes=15)
        self.assertEqual(self.execute(),0);self.assertEqual(self.reads,['drive'])
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertEqual(agenda.describe(self.config,state,self.clock)['drive']['next_due_utc'],before)
    def test_exact_recurrent_and_extra_are_one_read(self):
        self.set(day='2026-10-24',time='22:00');self.clock=datetime(2026,10,25,1,tzinfo=timezone.utc)
        self.assertEqual(self.execute(),0);self.assertEqual(self.reads,['cnrt'])
        self.assertNotIn('cnrt',agenda.select_jobs(self.config,self.config,json.loads((self.root/'_ftr_estado.json').read_text()),'scheduled',self.clock))
    def test_manual_and_due_extra_share_one_read_and_duplicate_request(self):
        self.set();self.clock+=timedelta(minutes=15);requested=self.clock.isoformat();identifier='c'*32
        self.assertEqual(self.execute('cnrt',dict(requested_utc=requested),identifier),0)
        self.assertEqual(self.execute('cnrt',dict(requested_utc=requested),identifier,run='102'),0)
        self.assertEqual(self.execute(run='103'),0);self.assertEqual(self.reads,['cnrt'])
    def test_manual_requested_while_source_running_shares_result(self):
        self.set();self.clock+=timedelta(minutes=15);requested=(self.clock+timedelta(minutes=2)).isoformat()
        self.assertEqual(self.execute(),0)
        self.assertEqual(self.execute('cnrt',dict(requested_utc=requested),'d'*32,run='102'),0);self.assertEqual(self.reads,['cnrt'])
    def test_source_failure_retains_valid_data_and_recurrence(self):
        self.set();self.clock+=timedelta(minutes=15);self.failing.add('cnrt')
        csv=(self.root/'parques/linea36.csv').read_bytes();stamp=(self.root/'ultima_actualizacion_parque.txt').read_bytes()
        before=agenda.describe(self.config,self.state,self.clock)['cnrt']['next_due_utc']
        self.assertEqual(self.execute(),1);self.assertEqual((self.root/'parques/linea36.csv').read_bytes(),csv);self.assertEqual((self.root/'ultima_actualizacion_parque.txt').read_bytes(),stamp)
        self.assertEqual(oneoff.load(self.root)['history'][-1]['status'],'error')
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertEqual(agenda.describe(self.config,state,self.clock)['cnrt']['next_due_utc'],before)
        self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['cnrt'])
    def test_delayed_event_is_consumed_once_without_other_source(self):
        self.set();self.clock+=timedelta(hours=3);self.assertEqual(self.execute(),0);self.assertEqual(self.reads,['cnrt'])
        self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['cnrt'])
    def test_next_year_cron_cannot_replay_abandoned_old_date(self):
        self.set();self.clock+=timedelta(days=365);self.assertEqual(self.execute(),1);self.assertEqual(self.reads,[])
        self.assertEqual(oneoff.load(self.root)['history'][-1]['status'],'error')
    def test_drive_extra_then_same_recurrent_event_is_coalesced(self):
        self.set('drive',day='2026-10-22',time='17:00');self.clock=datetime(2026,10,22,20,tzinfo=timezone.utc)
        self.assertEqual(self.execute(),0)
        state=json.loads((self.root/'_ftr_estado.json').read_text())
        base=ejecutar.sources_for_execution('scheduled',self.config,[],'schedule',state,self.clock)
        result=oneoff.resolve(self.root,'scheduled',self.config,state,base,self.clock,cron='0 20 * * *')
        self.assertNotIn('drive',result['jobs']);self.assertIn('drive',result['shared'])
        self.assertEqual(len(oneoff.load(self.root)['history'][-1]['reasons']),2)
        later=oneoff.resolve(self.root,'scheduled',self.config,state,base,self.clock,cron='0 3 * * *')
        self.assertIn('drive',later['jobs'])
    def test_interrupted_claim_is_error_without_retry(self):
        self.set();self.clock+=timedelta(minutes=15)
        plan=oneoff.resolve(self.root,'oneoff',self.config,self.state,[],self.clock)
        oneoff.claim(self.root,plan,self.clock,'101',self.commit)
        self.assertEqual(self.execute('cnrt',dict(requested_utc=self.clock.isoformat()),'b'*32,run='102'),1)
        self.clock+=timedelta(hours=2)
        recovered=oneoff.resolve(self.root,'oneoff',self.config,self.state,[],self.clock)
        self.assertEqual(recovered['data']['history'][-1]['status'],'error');self.assertFalse(recovered['jobs']);self.assertFalse(self.reads)
    def test_worker_program_and_cancel_never_touch_sources_or_data(self):
        protected={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p.name not in (oneoff.FILE,'ftr_extraordinarias.yml')}
        payload=dict(source='drive',date='2026-10-21',time='18:00',expected_id=None)
        self.assertEqual(self.execute('oneoff-set',payload,'a'*32),0)
        self.assertEqual(self.execute('oneoff-cancel',dict(source='drive',expected_id='a'*32),'b'*32),0)
        self.assertEqual({p:p.read_bytes() for p in protected},protected);self.assertFalse(self.reads)
    def test_claim_failure_never_reads_source(self):
        self.set();self.clock+=timedelta(minutes=15)
        self.commit=lambda *a:(_ for _ in ()).throw(ValueError('Conflicto de Git ficticio'))
        self.assertEqual(self.execute(),1);self.assertEqual(self.reads,[])
    def test_command_requires_workflow_authorization_before_writing(self):
        before=(self.root/oneoff.FILE).read_bytes()
        with patch.object(oneoff.native_schedule,'authorization',side_effect=ValueError('Permiso ficticio ausente')):
            with self.assertRaises(ValueError):self.set()
        self.assertEqual(before,(self.root/oneoff.FILE).read_bytes());self.assertEqual(self.reads,[])
    def test_pending_future_crossed_during_read_is_coalesced(self):
        self.set(time='17:48');requested=self.clock.isoformat()
        self.assertEqual(self.execute('cnrt',dict(requested_utc=requested),'e'*32),0)
        self.assertFalse(oneoff.load(self.root)['pending']);self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['cnrt'])


if __name__=='__main__':unittest.main()
