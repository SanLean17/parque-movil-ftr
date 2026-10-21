import unittest
from datetime import timedelta
from _ftr_app import test_outbox as fixtures
from _ftr_runtime import oneoff


class OneoffOutboxTests(unittest.TestCase):
    setUp=fixtures.OutboxTests.setUp
    tearDown=fixtures.OutboxTests.tearDown
    new_queue=fixtures.OutboxTests.new_queue
    row=fixtures.OutboxTests.row
    found=fixtures.OutboxTests.found

    def add(self,key='cnrt',**values):
        self.remote['oneoffs']=oneoff.empty()
        return self.queue.enqueue(dict(action='oneoff-set',oneoff=dict(source=key,date='2026-10-21',time='18:00',expected_id=None,**values)),self.remote)
    def test_offline_future_order_persists_and_dispatches_once(self):
        row=self.add();self.snapshot.side_effect=OSError('sin conexión');self.queue.tick()
        self.assertEqual(self.row()['status'],'pending');self.dispatch.assert_not_called()
        self.snapshot.side_effect=None;self.queue=self.new_queue();self.queue.tick();self.queue.tick()
        self.dispatch.assert_called_once();self.assertEqual(self.dispatch.call_args.args[0]['oneoff']['source'],'cnrt')
        self.found(row,effect='oneoff_saved');self.queue.tick();self.assertEqual(self.row()['status'],'completed')
    def test_offline_order_expires_without_dispatch(self):
        self.add();self.snapshot.side_effect=OSError('sin conexión');self.queue.tick();self.now+=timedelta(hours=4)
        self.snapshot.side_effect=None;self.queue.tick();self.dispatch.assert_not_called()
        self.assertEqual(self.row()['status'],'conflict');self.assertEqual(self.row()['message'],oneoff.EXPIRED)
    def test_each_source_can_have_one_order_and_change_does_not_stack(self):
        self.add('drive');self.add('cnrt');self.assertEqual(len(self.queue.read()['orders']),2)
        with self.assertRaisesRegex(ValueError,'Ya hay una orden'):
            self.queue.enqueue(dict(action='oneoff-set',oneoff=dict(source='cnrt',date='2026-10-22',time='09:00',expected_id=None)),self.remote)
    def test_stale_remote_schedule_is_not_overwritten(self):
        self.add();self.remote['oneoffs']['pending']['cnrt']=dict(id='b'*32)
        self.queue.tick();self.assertEqual(self.row()['status'],'conflict');self.dispatch.assert_not_called()
    def test_cancel_pending_local_order_does_not_dispatch(self):
        row=self.add();self.queue.cancel(row['id']);self.queue.tick();self.dispatch.assert_not_called();self.assertEqual(self.row()['status'],'cancelled')
    def test_remote_cancellation_has_no_date_and_is_explicit(self):
        self.remote['oneoffs']=oneoff.empty();self.remote['oneoffs']['pending']['drive']=dict(id='a'*32)
        row=self.queue.enqueue(dict(action='oneoff-cancel',oneoff=dict(source='drive',expected_id='a'*32)),self.remote)
        self.queue.tick();self.assertEqual(self.dispatch.call_args.args[0]['action'],'oneoff-cancel')
        self.found(row,effect='oneoff_saved');self.queue.tick();self.assertEqual(self.row()['status'],'completed')
