"""Turnos, entrega, recuperación y estado remoto con fuentes/GitHub simulados."""
import base64
import copy
import json
import os
import unittest
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import yaml
from _ftr_runtime import agenda,oneoff,worker,publication_retry,schedule_health,native_schedule
from _ftr_runtime.config import current_slot,digest
from _ftr_runtime import test_oneoff as fixtures
from _ftr_tools import ejecutar

ROOT=Path(__file__).resolve().parents[1]
def at(value):return datetime.fromisoformat(value+'-03:00')


class RecoveryTests(unittest.TestCase):
    setUp=fixtures.OneoffTests.setUp
    tearDown=fixtures.OneoffTests.tearDown
    commit=fixtures.OneoffTests.commit
    set=fixtures.OneoffTests.set

    def pending_drive(self):
        self.state['drive']=dict(status='success',read_utc=at('2026-10-20T17:00').isoformat(),served_slot=current_slot(self.config,'drive',at('2026-10-20T17:00')))
        (self.root/'_ftr_estado.json').write_text(json.dumps(self.state))

    def execute(self,mode='recovery',run='101',pages=None,created=None):
        with ExitStack() as s:
            env=dict(FTR_ACTION=mode,FTR_CONFIG='{}',FTR_REQUEST_ID='',GITHUB_REF='refs/heads/main',GITHUB_REPOSITORY='SanLean17/parque-movil-ftr',GITHUB_RUN_ID=run)
            if created:env['FTR_EVENT_CREATED_UTC']=created
            s.enter_context(patch.dict(os.environ,env,clear=True))
            s.enter_context(patch.object(worker,'ROOT',self.root));s.enter_context(patch.object(worker,'REPORT_DIR',Path(self.temp.name)/'report'))
            s.enter_context(patch.object(worker,'now',side_effect=lambda:self.clock));s.enter_context(patch.object(worker,'plan',ejecutar._original_plan));s.enter_context(patch.object(worker,'selected',agenda.select_jobs))
            s.enter_context(patch.object(worker,'commit',side_effect=self.commit));s.enter_context(patch.object(worker,'build_pages',side_effect=pages))
            s.enter_context(patch.object(publication_retry,'current_revision',return_value='f'*40))
            def read(key,root,config):
                self.reads.append(key);started=self.clock.isoformat();self.clock+=timedelta(minutes=5)
                if key in self.failing:raise ValueError('Fuente ficticia no disponible')
                folder,stamp=('parques','ultima_actualizacion_parque.txt') if key=='cnrt' else ('controlados','ultima_actualizacion_controlados.txt')
                (root/folder/'linea36.csv').write_text('dominio,interno,linea\nBB222BB,1,36\n')
                (root/stamp).write_text(started)
                if key=='drive':(root/'estadisticas_ftr.json').write_text('{"fixture_agenda":true}')
                return dict(read_utc=started,completed_utc=self.clock.isoformat(),period=2026)
            s.enter_context(patch.object(worker,'google_snapshot',side_effect=lambda r,c:read('drive',r,c)))
            s.enter_context(patch.object(worker,'cnrt_snapshot',side_effect=lambda r,c:read('cnrt',r,c)))
            return worker.main()

    def test_exact_daily_turn_and_duplicate_do_not_read_again(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00');self.assertEqual(self.execute(),0)
        self.assertEqual(self.reads,['drive']);self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['drive'])
        trace=oneoff.load(self.root)['execution_history'][-1];self.assertEqual(trace['expected_utc'],at('2026-10-21T17:00').astimezone(timezone.utc).isoformat());self.assertEqual(trace['delay_seconds'],0)
    def test_two_minutes_late_reports_real_delay(self):
        self.pending_drive();self.clock=at('2026-10-21T17:02');self.assertEqual(self.execute('scheduled'),0)
        trace=oneoff.load(self.root)['execution_history'][-1];self.assertEqual(trace['kind'],'delayed');self.assertEqual(trace['delay_seconds'],120)
    def test_thirty_minutes_late_is_overdue_then_recovered(self):
        self.pending_drive();self.clock=at('2026-10-21T17:30')
        self.assertEqual(agenda.describe(self.config,self.state,self.clock)['drive']['status'],'overdue')
        self.assertEqual(self.execute(),0);self.assertEqual(oneoff.load(self.root)['execution_history'][-1]['kind'],'recovered')
    def test_missed_turn_recovers_after_midnight_without_forcing_cnrt(self):
        self.pending_drive();self.clock=at('2026-10-22T00:22');self.assertEqual(self.execute(),0);self.assertEqual(self.reads,['drive'])
        self.assertEqual(oneoff.load(self.root)['execution_history'][-1]['expected_utc'],at('2026-10-21T17:00').astimezone(timezone.utc).isoformat())
    def test_extra_before_hour_does_not_satisfy_principal(self):
        self.pending_drive();self.clock=at('2026-10-21T16:00');self.set('drive',time='16:15');self.clock=at('2026-10-21T16:15')
        self.assertEqual(self.execute('oneoff'),0);self.clock=at('2026-10-21T17:00');self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['drive','drive'])
    def test_extra_after_hour_does_not_satisfy_principal(self):
        self.pending_drive();self.clock=at('2026-10-21T17:45');self.set('drive',time='18:00');self.clock=at('2026-10-21T18:00')
        self.assertEqual(self.execute('oneoff'),0);self.clock=at('2026-10-21T18:22');self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['drive','drive'])
    def test_exact_extra_and_recovery_are_one_source_read(self):
        self.pending_drive();self.clock=at('2026-10-21T16:45');self.set('drive',time='17:00');self.clock=at('2026-10-21T17:00')
        self.assertEqual(self.execute(),0);self.assertEqual(self.execute('oneoff',run='102'),0);self.assertEqual(self.reads,['drive'])
    def test_manual_coincident_then_primary_does_not_duplicate(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00');self.assertEqual(self.execute('drive'),0)
        state=json.loads((self.root/'_ftr_estado.json').read_text());base=agenda.select_jobs(self.config,self.config,state,'scheduled',self.clock)
        self.assertEqual(ejecutar.sources_for_execution('scheduled',self.config,base,'schedule',state,self.clock,'0 20 * * *'),[])
        self.assertEqual(ejecutar.sources_for_execution('scheduled',self.config,base,'schedule',state,self.clock,'0 3 * * *'),['drive'])
    def test_duplicate_event_id_cannot_repeat_additional_read(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00');self.assertEqual(self.execute('drive'),0)
        plan=oneoff.resolve(self.root,'scheduled',self.config,self.state,['drive'],self.clock,run_id='101')
        self.assertFalse(plan['jobs']);self.assertIn('drive',plan['shared'])
    def test_queued_event_shares_existing_source_result(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00');created=(self.clock+timedelta(minutes=1)).isoformat();self.execute('drive')
        state=json.loads((self.root/'_ftr_estado.json').read_text())
        plan=oneoff.resolve(self.root,'scheduled',self.config,state,['drive'],self.clock,event_created=created,run_id='102')
        self.assertFalse(plan['jobs'])
    def test_event_created_during_early_read_still_reads_after_main_hour(self):
        self.pending_drive();self.clock=at('2026-10-21T16:58');self.assertEqual(self.execute('drive'),0)
        self.assertEqual(self.execute(run='102',created=at('2026-10-21T17:00').isoformat()),0)
        self.assertEqual(self.reads,['drive','drive'])
    def test_failed_publication_recovers_without_re_reading(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00')
        self.assertEqual(self.execute(pages=ValueError('Publicación ficticia fallida')),1)
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertTrue(publication_retry.pending(state));before=state['drive'].copy()
        self.clock+=timedelta(minutes=20);self.assertEqual(self.execute(run='102'),0)
        after=json.loads((self.root/'_ftr_estado.json').read_text());self.assertEqual(after['drive'],before);self.assertEqual(after['publication']['status'],'success');self.assertEqual(self.reads,['drive'])
    def test_cancelled_claim_recovers_after_bounded_timeout(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00')
        plan=oneoff.resolve(self.root,'recovery',self.config,self.state,['drive'],self.clock)
        oneoff.claim(self.root,plan,self.clock,'100',self.commit);self.clock+=timedelta(minutes=96)
        self.assertEqual(self.execute(run='101',created=self.clock.isoformat()),0);history=oneoff.load(self.root)['execution_history']
        self.assertEqual(history[-2]['status'],'error');self.assertEqual(self.reads,['drive'])
    def test_source_error_keeps_valid_file_and_retry_wait(self):
        self.pending_drive();self.clock=at('2026-10-21T17:00');self.failing.add('drive');before=(self.root/'controlados/linea36.csv').read_bytes()
        self.assertEqual(self.execute(),1);self.assertEqual((self.root/'controlados/linea36.csv').read_bytes(),before)
        self.clock+=timedelta(minutes=15);self.assertEqual(self.execute(run='102'),0);self.assertEqual(self.reads,['drive'])
        self.clock+=timedelta(hours=1);self.failing.clear();self.assertEqual(self.execute(run='103'),0);self.assertEqual(self.reads,['drive','drive'])
    def test_three_and_five_day_cnrt_across_month_and_year(self):
        for days in (3,5):
            c=copy.deepcopy(self.config);c['anchor']='2026-12-29';c['cnrt']['days']=days
            start=at('2026-12-29T22:00');s={'cnrt':dict(status='success',read_utc=start.isoformat(),served_slot=current_slot(c,'cnrt',start))}
            due=start+timedelta(days=days)
            self.assertNotIn('cnrt',agenda.select_jobs(c,c,s,'recovery',due-timedelta(minutes=1)))
            self.assertIn('cnrt',agenda.select_jobs(c,c,s,'recovery',due))
            self.assertEqual(agenda.slot_time(current_slot(c,'cnrt',due)).astimezone(timezone.utc).hour,1)
    def test_same_and_different_hours_do_not_force_other_source(self):
        c=copy.deepcopy(self.config);moment=at('2026-10-24T17:00')
        c['cnrt']['time']='17:00';self.assertEqual(set(agenda.select_jobs(c,c,{},'recovery',moment)),{'drive','cnrt'})
        c['cnrt']['time']='22:00';state={'cnrt':self.state['cnrt']};self.assertNotIn('cnrt',agenda.select_jobs(c,c,state,'recovery',moment))
    def test_finish_after_hour_does_not_serve_turn_started_before(self):
        self.pending_drive();self.clock=at('2026-10-21T16:58');self.assertEqual(self.execute('drive'),0)
        state=json.loads((self.root/'_ftr_estado.json').read_text());self.assertIn('drive',agenda.select_jobs(self.config,self.config,state,'recovery',self.clock))
    def test_new_frequency_has_new_fingerprint_and_old_read_stays_old(self):
        old=copy.deepcopy(self.config);self.config['cnrt']['days']=3
        agenda.activate_changed_schedules(old,self.config,self.state,at('2026-10-21T17:00'))
        self.assertIn('cnrt',agenda.select_jobs(self.config,self.config,self.state,'recovery',at('2026-10-22T22:00')))
    def test_clock_change_removes_old_cron_and_has_correct_utc(self):
        c=copy.deepcopy(self.config);c['drive']['time']='18:30';text=native_schedule.render(c)
        self.assertIn("'30 21 * * *'",text);self.assertNotIn("'0 20 * * *'",text);self.assertIn("'0 1 * * *'",text)
    def test_recovery_does_not_add_reads_after_satisfied_turn(self):
        self.assertEqual(agenda.select_jobs(self.config,self.config,self.state,'recovery',self.clock),[])
        self.assertEqual(ejecutar.sources_for_execution('recovery',self.config,[],'schedule',self.state,self.clock),[])


class RemoteHealthTests(unittest.TestCase):
    def setUp(self):
        from _ftr_runtime.config import load
        self.config=load(ROOT);self.extra=oneoff.empty();self.disabled=None;self.denied=False;self.branch='main';self.mismatch=False
    def get(self,path):
        if self.denied:raise ValueError('Permiso simulado denegado')
        if not path:return dict(default_branch=self.branch)
        if '/runs?' in path:return dict(workflow_runs=[])
        if path.startswith('actions/'):return dict(state='disabled_manually' if path.endswith(self.disabled or '_none_') else 'active')
        content=(native_schedule.render(self.config) if native_schedule.PATH in path else native_schedule.render_recovery() if native_schedule.RECOVERY_PATH in path else oneoff.render(self.extra))
        if self.mismatch:content+='bad'
        return dict(content=base64.b64encode(content.encode()).decode())
    def test_active_requires_real_workflows_and_exact_published_calendar(self):
        self.assertEqual(schedule_health.inspect(self.config,self.extra,'a'*40,self.get)['status'],'active')
    def test_disabled_is_never_shown_as_active(self):
        self.disabled='actualizar_parques.yml';self.assertEqual(schedule_health.inspect(self.config,self.extra,'a'*40,self.get)['status'],'disabled')
    def test_missing_permissions_is_unknown_not_active(self):
        self.denied=True;self.assertEqual(schedule_health.inspect(self.config,self.extra,'a'*40,self.get)['status'],'unknown')
    def test_wrong_default_branch_and_wrong_cron_are_rejected(self):
        self.branch='other';self.assertEqual(schedule_health.inspect(self.config,self.extra,'a'*40,self.get)['status'],'mismatch')
        self.branch='main';self.mismatch=True;self.assertEqual(schedule_health.inspect(self.config,self.extra,'a'*40,self.get)['status'],'mismatch')
    def test_saved_config_does_not_report_enabled_when_remote_disabled(self):
        self.disabled='actualizar_parques.yml'
        with patch.dict(os.environ,{'GITHUB_TOKEN':'FICTICIO'}),patch.object(schedule_health,'github_get',side_effect=self.get):
            with self.assertRaisesRegex(ValueError,'no confirmó'):schedule_health.confirm(ROOT,self.config,'a'*40)
    def test_single_queue_preserves_all_callers_and_no_push_sources(self):
        files=['actualizar_parques.yml','ftr_recuperar_turnos.yml','ftr_extraordinarias.yml','ftr_sincronizar.yml']
        docs={name:yaml.load((ROOT/'.github/workflows'/name).read_text(encoding='utf-8-sig'),Loader=yaml.BaseLoader) for name in files}
        child=docs['ftr_sincronizar.yml'];self.assertEqual(child['concurrency'],{'group':'ftr-publicacion-validada','cancel-in-progress':'false','queue':'max'})
        for name,data in docs.items():
            self.assertNotIn('push',data['on'])
            if name!='ftr_sincronizar.yml':self.assertNotIn('concurrency',data)
        self.assertEqual(docs['ftr_recuperar_turnos.yml']['on']['schedule'][0]['cron'],'7,22,37,52 * * * *')
        self.assertEqual(docs['ftr_recuperar_turnos.yml']['jobs']['comprobar']['with']['action'],'recovery')
