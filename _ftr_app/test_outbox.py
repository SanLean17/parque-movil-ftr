"""Recuperación de órdenes: disco real, GitHub simulado, sin credenciales."""
import copy
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock

from _ftr_app.outbox import Outbox, AuthorizationError
from _ftr_runtime.config import load, digest


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = load(Path(__file__).resolve().parents[1])
        from _ftr_runtime import dictionary_rules as rules
        self.remote = dict(config=self.config, digest=digest(self.config),dictionary_digest=rules.digest(rules.EMPTY))
        self.now = datetime(2026, 10, 21, 18, tzinfo=timezone.utc)
        self.snapshot = Mock(return_value=self.remote)
        self.runs = Mock(return_value=[])
        self.dispatch = Mock()
        self.queue = self.new_queue()

    def tearDown(self):
        self.temp.cleanup()

    def new_queue(self):
        return Outbox(lambda: self.root, self.snapshot, self.runs, self.dispatch, lambda: self.now)

    def add(self, action='drive', **kw):
        return self.queue.enqueue(dict(action=action, **kw), self.remote)

    def row(self, pos=0):
        return self.queue.read()['orders'][pos]

    def found(self, row, status='completed', effect='updated', conclusion='success'):
        self.runs.return_value = [dict(id=123, request_id=row['id'], status=status, effect=effect, conclusion=conclusion)]

    def test_draft_and_open_without_orders_never_send(self):
        (self.root/'borrador.json').write_text(json.dumps(self.config))
        self.queue.tick()
        self.snapshot.assert_not_called()
        self.dispatch.assert_not_called()

    def test_offline_close_reopen_once(self):
        row = self.add()
        self.snapshot.side_effect = OSError('offline')
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'pending')
        self.dispatch.assert_not_called()
        self.snapshot.side_effect = None
        self.queue = self.new_queue()
        self.queue.tick()
        self.queue.tick()
        self.dispatch.assert_called_once()
        self.assertEqual(self.dispatch.call_args.args[0]['id'], row['id'])
        self.assertEqual(self.row()['status'], 'sent')

    def test_lost_response_never_resent_and_result_recovered(self):
        row = self.add()
        self.dispatch.side_effect = TimeoutError('unknown acceptance')
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'unknown')
        self.queue = self.new_queue()
        for _ in range(4):
            self.queue.tick()
        self.dispatch.assert_called_once()
        self.found(row)
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'completed')
        self.dispatch.assert_called_once()

    def test_crash_after_post_preparation_not_replayed(self):
        row = self.add()
        stored = self.queue.read()
        stored['orders'][0]['status'] = 'sending'
        self.queue.save(stored)
        self.queue = self.new_queue()
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'unknown')
        self.dispatch.assert_not_called()
        self.found(row, status='in_progress')
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'sent')

    def test_cancel_unsent_and_reopen(self):
        row = self.add()
        self.queue.cancel(row['id'])
        self.new_queue().tick()
        self.dispatch.assert_not_called()
        self.assertEqual(self.row()['status'], 'cancelled')

    def test_cannot_claim_cancellation_after_send(self):
        row = self.add()
        self.queue.tick()
        with self.assertRaisesRegex(ValueError, 'todavía no'):
            self.queue.cancel(row['id'])

    def test_two_computers_config_conflict_preserves_order(self):
        self.add('config', config=self.config)
        changed = copy.deepcopy(self.config)
        changed['drive']['time'] = '18:30'
        self.snapshot.return_value = dict(config=changed, digest=digest(changed))
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'conflict')
        self.assertEqual(self.row()['config'], self.config)
        self.dispatch.assert_not_called()

    def test_manual_read_also_bound_to_reviewed_configuration(self):
        self.add()
        self.snapshot.return_value = dict(digest='b'*64)
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'conflict')
        self.dispatch.assert_not_called()

    def test_dependent_read_waits_for_config_publication(self):
        changed = copy.deepcopy(self.config)
        changed['cnrt']['days'] = 3
        parent = self.add('config', config=changed)
        child = self.add('all', depends_on=parent['id'])
        self.queue.tick()
        self.dispatch.assert_called_once()
        self.assertEqual(self.dispatch.call_args.args[0]['action'], 'config')
        self.found(parent, effect='configuration')
        self.snapshot.return_value = dict(config=changed, digest=digest(changed))
        self.queue.tick()
        self.assertEqual(self.dispatch.call_count, 2)
        self.assertEqual(self.dispatch.call_args.args[0]['id'], child['id'])
        self.assertEqual(self.dispatch.call_args.args[0]['expected'], digest(changed))

    def test_failed_config_blocks_dependent_read(self):
        parent = self.add('config', config=self.config)
        self.add('all', depends_on=parent['id'])
        self.queue.tick()
        self.found(parent, effect='failed', conclusion='failure')
        self.queue.tick()
        self.assertEqual(self.row(1)['status'], 'conflict')
        self.dispatch.assert_called_once()

    def test_expired_credential_preserves_then_sends(self):
        self.add()
        self.snapshot.side_effect = AuthorizationError('expired')
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'authorization')
        self.dispatch.assert_not_called()
        self.snapshot.side_effect = None
        self.queue.reconnected()
        self.queue.tick()
        self.dispatch.assert_called_once()

    def test_rejected_dispatch_can_retry_after_reconnect(self):
        self.add()
        self.dispatch.side_effect = AuthorizationError('HTTP 401')
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'authorization')
        self.dispatch.side_effect = None
        self.queue.reconnected()
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'sent')

    def test_duplicate_clicks_share_one_order_and_dispatch(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: self.add(), range(20)))
        self.assertEqual(len({r['id'] for r in rows}), 1)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.queue.tick(), range(20)))
        self.dispatch.assert_called_once()

    def test_busy_remote_waits_without_dropping(self):
        self.add()
        self.runs.return_value = [dict(id=1, status='in_progress')]
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'pending')
        self.dispatch.assert_not_called()

    def test_old_orders_require_review(self):
        self.add()
        self.now += timedelta(days=8)
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'conflict')
        self.dispatch.assert_not_called()

    def test_corrupt_file_is_not_silently_reset(self):
        file = self.root/'ordenes.json'
        file.write_text('{broken')
        with self.assertRaises(ValueError):
            self.queue.tick()
        self.assertEqual(file.read_text(), '{broken')
        self.dispatch.assert_not_called()

    def test_green_no_read_is_not_completion(self):
        row = self.add()
        self.queue.tick()
        self.found(row, effect='agenda_only')
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
