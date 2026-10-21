import base64
import copy
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_clock import LocalClock, computer_lock, read_json
from _ftr_runtime.config import load, current_slot
ROOT=Path(__file__).resolve().parents[1]

class ClockTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.cfg=load(ROOT);self.cfg['drive'].update(time='22:00',days=1,enabled=True)
        self.cfg['cnrt'].update(time='22:00',days=5,enabled=True);self.cfg['anchor']='2026-10-19'
        self.now=datetime(2026,10,21,0,59,59,tzinfo=timezone.utc)
        yesterday=datetime(2026,10,20,1,0,tzinfo=timezone.utc)
        self.state={key:dict(status='success',read_utc=yesterday.isoformat(),served_slot=current_slot(self.cfg,key,yesterday)) for key in ('drive','cnrt')}
        self.state['drive']['schedule_effective_from_utc']='2026-10-21T00:50:55+00:00'
        self.sender=Mock();self.runs=Mock(return_value=[]);self.snapshot=Mock(side_effect=lambda:(copy.deepcopy(self.cfg),copy.deepcopy(self.state),'a'*40))
        self.clock=LocalClock(lambda:self.root,self.snapshot,self.runs,self.sender,threading.Lock(),utcnow=lambda:self.now,interval=.01)
    def tearDown(self):self.clock.stop();self.temp.cleanup()
    def enable(self):self.clock.set_enabled(True)
    def test_disabled_by_default_and_no_network(self):
        self.clock.tick();self.snapshot.assert_not_called();self.sender.assert_not_called()
    def test_before_hour_does_not_send(self):
        self.enable();self.clock.tick();self.sender.assert_not_called()
    def test_at_hour_sends_drive_only_due(self):
        self.enable();self.now+=timedelta(seconds=1);self.clock.tick()
        self.sender.assert_called_once();self.assertEqual(self.clock.status()['sources'],['drive'])
    def test_due_but_not_cnrt_due_day(self):
        self.enable();self.now+=timedelta(hours=1);self.clock.tick()
        self.assertEqual(self.clock.status()['sources'],['drive'])
    def test_cnrt_due_day_included(self):
        self.enable();self.now=datetime(2026,10,25,1,0,tzinfo=timezone.utc);self.clock.tick()
        self.assertEqual(self.clock.status()['sources'],['cnrt','drive'])
    def test_second_tick_not_repeat(self):
        self.enable();self.now+=timedelta(seconds=1);self.clock.tick();self.clock.tick();self.sender.assert_called_once()
    def test_new_instance_uses_pending_receipt(self):
        self.enable();self.now+=timedelta(seconds=1);self.clock.tick()
        other=LocalClock(lambda:self.root,self.snapshot,self.runs,self.sender,threading.Lock(),utcnow=lambda:self.now)
        other.tick();self.sender.assert_called_once()
    def test_successful_read_deduplicated(self):
        self.enable();self.now+=timedelta(seconds=1);self.state['drive'].update(read_utc=self.now.isoformat(),served_slot=current_slot(self.cfg,'drive',self.now));self.clock.tick()
        self.sender.assert_not_called()
    def test_remote_busy_not_send(self):
        self.enable();self.now+=timedelta(seconds=1);self.runs.return_value=[{'status':'in_progress'}];self.clock.tick();self.sender.assert_not_called()
    def test_remote_queued_not_send(self):
        self.enable();self.now+=timedelta(seconds=1);self.runs.return_value=[{'status':'queued'}];self.clock.tick();self.sender.assert_not_called()
    def test_config_job_blocks_as_well(self):
        self.enable();self.now+=timedelta(seconds=1);self.runs.return_value=[{'status':'waiting','display_title':'FTR · config · abc'}];self.clock.tick();self.sender.assert_not_called()
    def test_failed_send_not_resent_immediately(self):
        self.enable();self.now+=timedelta(seconds=1);self.sender.side_effect=RuntimeError('secret-token-never-display')
        self.clock.tick();self.clock.tick();self.sender.assert_called_once();self.assertNotIn('secret',str(self.clock.status()))
    def test_receipt_stored_before_send(self):
        self.enable();self.now+=timedelta(seconds=1)
        def send(identifier):self.assertEqual(read_json(self.root/'reloj_pc_envio.json',{})['request_id'],identifier)
        self.sender.side_effect=send;self.clock.tick();self.sender.assert_called_once()
    def test_failed_send_retries_after_ten_minutes(self):
        self.enable();self.now+=timedelta(seconds=1);self.sender.side_effect=RuntimeError();self.clock.tick();self.now+=timedelta(minutes=11);self.clock.tick();self.assertEqual(self.sender.call_count,2)
    def test_offline_does_not_dispatch_or_modify_config(self):
        self.enable();self.snapshot.side_effect=RuntimeError('private');self.clock.tick();self.sender.assert_not_called();self.assertEqual(self.clock.status()['status'],'error')
    def test_auth_missing_is_not_success(self):
        self.enable();self.snapshot.side_effect=ValueError('no token');self.clock.tick();self.assertEqual(self.clock.status()['status'],'error')
    def test_disabled_source_not_requested(self):
        self.enable();self.now+=timedelta(seconds=1);self.cfg['drive']['enabled']=False;self.clock.tick();self.sender.assert_not_called()
    def test_new_published_hour_used(self):
        self.enable();self.now+=timedelta(seconds=1);self.cfg['drive']['time']='23:00';self.clock.tick();self.sender.assert_not_called()
    def test_activating_overdue_turn_is_automatic(self):
        self.now+=timedelta(minutes=30);self.enable();self.clock.tick();self.sender.assert_called_once()
    def test_disabling_stops_new_dispatch(self):
        self.enable();self.now+=timedelta(seconds=1);self.clock.set_enabled(False);self.clock.tick();self.sender.assert_not_called()
    def test_no_config_or_csv_writes(self):
        self.enable();self.now+=timedelta(seconds=1);self.clock.tick()
        self.assertEqual({p.name for p in self.root.iterdir()},{'reloj_pc.json','reloj_pc_envio.json','reloj_pc.lock'})
    def test_loop_reacts_to_due_without_user_button(self):
        self.enable();self.clock.start();time.sleep(.04);self.sender.assert_not_called()
        self.now+=timedelta(seconds=1)
        deadline=time.monotonic()+2
        while not self.sender.called and time.monotonic()<deadline:time.sleep(.01)
        self.sender.assert_called_once()
    def test_status_does_not_dispatch(self):
        self.enable();self.now+=timedelta(seconds=1);self.clock.status();self.sender.assert_not_called()
    def test_real_cross_process_lock(self):
        with computer_lock(self.root/'test.lock') as first:
            self.assertTrue(first)
            with computer_lock(self.root/'test.lock') as second:self.assertFalse(second)
    def test_no_crash_on_corrupt_settings(self):
        (self.root/'reloj_pc.json').write_text('{broken');self.clock.tick();self.sender.assert_not_called()
    def test_non_boolean_not_accepted(self):
        with self.assertRaises(ValueError):self.clock.set_enabled('true')

class TransportTests(unittest.TestCase):
    def test_dispatch_is_scheduled_not_force_all(self):
        import main064
        with patch.object(main064.server,'api') as api:
            main064.dispatch('pc-auto-example')
            self.assertEqual(api.call_args.args[2]['inputs']['action'],'scheduled')
            self.assertEqual(api.call_args.args[2]['inputs']['config_json'],'')
    def test_snapshot_same_commit_and_no_draft(self):
        import main064
        cfg=load(ROOT)
        def payload(value):return {'content':base64.b64encode(json.dumps(value).encode()).decode()}
        with patch.object(main064.server,'api',side_effect=[{'object':{'sha':'b'*40}},payload(cfg),payload({})]) as api:
            c,s,rev=main064.snapshot()
            self.assertEqual(rev,'b'*40)
            self.assertTrue(all(('?ref='+'b'*40) in call.args[1] for call in api.call_args_list[1:]))
    def test_bad_revision_rejected(self):
        import main064
        with patch.object(main064.server,'api',return_value={'object':{'sha':'main?x'}}):
            with self.assertRaises(ValueError):main064.snapshot()

if __name__=='__main__':unittest.main()
