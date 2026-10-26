"""Recovery is explicit, keeps all evidence and never resends an uncertain POST."""
import copy
import unittest
from datetime import timedelta
from _ftr_app import test_outbox as fixtures
from _ftr_app.outbox import DispatchRejected
from _ftr_app.queue_runs import RunScan
from _ftr_runtime import dictionary_rules as rules

class RecoveryTests(unittest.TestCase):
    setUp=fixtures.OutboxTests.setUp
    tearDown=fixtures.OutboxTests.tearDown
    new_queue=fixtures.OutboxTests.new_queue
    add=fixtures.OutboxTests.add
    row=fixtures.OutboxTests.row
    found=fixtures.OutboxTests.found

    def uncertain(self):
        row=self.add();self.dispatch.side_effect=TimeoutError();self.queue.tick()
        self.now+=timedelta(minutes=6)
        self.runs.return_value=RunScan([],dict(complete=True,examined=350,requests=4))
        return row

    def test_lost_request_resolve_pause_review_resume_without_repeating(self):
        first=self.uncertain();second=self.add('diagnostic',config=self.config)
        for _ in range(3):self.new_queue().tick()
        self.dispatch.assert_called_once()
        self.queue.check(first['id']);confirmation=self.row()['resolution']['confirmation']
        self.queue.resolve(first['id'],confirmation)
        self.assertEqual(self.row()['status'],'resolved');self.assertEqual(len(self.row()['checks']),2)
        self.assertFalse(self.row()['publication_verified']);self.assertTrue(self.queue.status()['paused'])
        self.queue=self.new_queue();self.queue.tick();self.dispatch.assert_called_once()
        self.dispatch.side_effect=None
        self.queue.resume(self.queue.status()['confirmation']);self.dispatch.assert_called_once()
        self.queue.tick();self.assertEqual(self.dispatch.call_count,2)
        self.assertEqual(self.dispatch.call_args.args[0]['id'],second['id'])
        self.assertEqual(len(self.queue.read()['orders']),2)

    def test_accepted_but_response_lost_is_found_not_resent(self):
        first=self.uncertain();self.found(first,status='in_progress')
        self.queue.check(first['id']);self.assertEqual(self.row()['status'],'sent')
        self.assertIsNone(self.row()['resolution']);self.dispatch.assert_called_once()
        self.found(first);self.queue.check(first['id'])
        self.assertEqual(self.row()['status'],'completed');self.assertTrue(self.row()['publication_verified'])
        self.assertEqual(len(self.row()['checks']),2);self.dispatch.assert_called_once()

    def test_discovery_between_check_and_resolution_cannot_be_abandoned(self):
        first=self.uncertain();self.queue.check(first['id']);token=self.row()['resolution']['confirmation']
        self.found(first,status='queued')
        with self.assertRaisesRegex(ValueError,'resultado cambió'):self.queue.resolve(first['id'],token)
        self.assertEqual(self.row()['status'],'sent');self.assertFalse(self.queue.status()['paused'])

    def test_offline_incomplete_or_stale_check_never_allows_resolution(self):
        first=self.uncertain();self.runs.side_effect=OSError('offline')
        self.queue.check(first['id']);self.assertIsNone(self.row()['resolution'])
        self.assertFalse(self.row()['checks'][-1]['complete'])
        with self.assertRaises(ValueError):self.queue.resolve(first['id'],'fake')
        self.runs.side_effect=None;self.runs.return_value=[]
        self.queue.check(first['id']);self.assertIsNone(self.row()['resolution'])
        self.runs.return_value=RunScan([],dict(complete=True));self.queue.check(first['id'])
        token=self.row()['resolution']['confirmation'];self.now+=timedelta(minutes=6)
        with self.assertRaisesRegex(ValueError,'venció'):self.queue.resolve(first['id'],token)
        self.dispatch.assert_called_once()

    def test_explicit_http_rejection_is_not_uncertain_and_can_be_cancelled(self):
        first=self.add();self.dispatch.side_effect=DispatchRejected(422);self.queue.tick()
        self.assertEqual(self.row()['status'],'conflict');self.assertEqual(self.row()['dispatch_evidence'][0]['http_status'],422)
        self.queue.tick();self.dispatch.assert_called_once();self.queue.cancel(first['id'])
        self.assertEqual(self.row()['status'],'cancelled')

    def test_dictionary_success_then_stale_second_rule_stops_before_post(self):
        payload=dict(expected_dictionary=rules.digest(rules.EMPTY),reglas=[dict(expresion='X12',categoria='direccion',componente='barra_larga',habilitada=True)])
        first=self.queue.enqueue(dict(action='dictionary-save',statistical=payload),self.remote)
        payload=copy.deepcopy(payload);payload['reglas'][0]['expresion']='X13'
        second=self.queue.enqueue(dict(action='dictionary-save',statistical=payload),self.remote)
        self.queue.tick();self.found(first,effect='dictionary')
        self.snapshot.return_value=dict(self.remote,dictionary_digest='c'*64)
        self.queue.tick();self.dispatch.assert_called_once()
        self.assertEqual(self.row(1)['status'],'conflict');self.assertIn('diccionario',self.row(1)['message'])
        self.assertEqual(self.row(1)['id'],second['id'])

    def test_resolution_blocks_dependent_config_and_resume_checks_current_remote(self):
        parent=self.add('config',config=self.config);self.add('drive',depends_on=parent['id'])
        self.dispatch.side_effect=TimeoutError();self.queue.tick();self.now+=timedelta(minutes=6)
        self.runs.return_value=RunScan([],dict(complete=True));self.queue.check(parent['id'])
        self.queue.resolve(parent['id'],self.row()['resolution']['confirmation'])
        self.assertEqual(self.row(1)['status'],'conflict')
        with self.assertRaises(ValueError):self.queue.resume(self.queue.status()['confirmation'])
        self.queue.cancel(self.row(1)['id']);self.add('drive')
        self.snapshot.return_value=dict(self.remote,digest='b'*64)
        with self.assertRaisesRegex(ValueError,'configuración'):self.queue.resume(self.queue.status()['confirmation'])
        self.assertTrue(self.queue.status()['paused']);self.dispatch.assert_called_once()

    def test_duplicate_matches_do_not_confirm_success_or_offer_resolution(self):
        first=self.uncertain();self.found(first)
        self.runs.return_value=RunScan(self.runs.return_value*2,dict(complete=True))
        self.queue.check(first['id']);self.assertEqual(self.row()['status'],'unknown')
        self.assertIsNone(self.row()['resolution']);self.dispatch.assert_called_once()

    def test_restart_retains_original_id_payload_history_and_unknown(self):
        first=self.uncertain();before=copy.deepcopy(self.row());self.queue=self.new_queue()
        self.assertEqual(self.row(),before);self.queue.tick();self.dispatch.assert_called_once()
        with self.assertRaises(ValueError):self.queue.cancel(first['id'])

    def test_bad_local_dictionary_is_conflict_before_dispatch(self):
        first=self.add();value=self.queue.read();value['orders'][0].update(action='dictionary-save',statistical={})
        self.queue.save(value);self.queue.tick();self.dispatch.assert_not_called()
        self.assertEqual(self.row()['status'],'conflict');self.assertEqual(self.row()['attempts'],0)

    def test_recent_or_tampered_confirmation_cannot_close_order(self):
        first=self.uncertain();self.now-=timedelta(minutes=5)
        self.queue.check(first['id']);self.assertIsNone(self.row()['resolution'])
        self.now+=timedelta(minutes=5);self.queue.check(first['id'])
        with self.assertRaises(ValueError):self.queue.resolve(first['id'],'tampered')
        self.assertEqual(self.row()['status'],'unknown')

    def test_closed_history_and_later_success_do_not_make_a_current_blocker(self):
        first=self.add();second=self.add('cnrt');third=self.add('diagnostic',config=self.config)
        value=self.queue.read();value['paused']=True
        for row,status in zip(value['orders'],('resolved','cancelled','completed')):row['status']=status
        self.queue.save(value);raw=(self.root/'ordenes.json').read_bytes()
        self.queue=self.new_queue();status=self.queue.status();self.queue.tick()
        self.assertIsNone(status['blocked']);self.assertTrue(status['paused'])
        self.assertEqual([r['id'] for r in status['orders']],[first['id'],second['id'],third['id']])
        self.assertEqual((self.root/'ordenes.json').read_bytes(),raw)
        self.snapshot.assert_not_called();self.dispatch.assert_not_called()

    def test_later_request_success_cannot_confirm_another_identifier(self):
        first=self.uncertain();later=dict(first,id='f'*32);self.found(later)
        self.runs.return_value=RunScan(self.runs.return_value,dict(complete=True))
        self.queue.check(first['id'])
        self.assertEqual(self.row()['status'],'unknown')
        self.assertFalse(self.row().get('publication_verified',False))
        self.assertEqual(self.row()['checks'][-1]['result'],'not_found')
        self.dispatch.assert_called_once()
