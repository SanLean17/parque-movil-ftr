"""Interrupciones sin turnos nuevos: fuentes y publicación completamente simuladas."""
import os
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from _ftr_runtime import oneoff, worker
from _ftr_runtime import test_recovery as fixtures


class InterruptedHistoryTests(unittest.TestCase):
    setUp = fixtures.RecoveryTests.setUp
    tearDown = fixtures.RecoveryTests.tearDown
    commit = fixtures.RecoveryTests.commit
    set = fixtures.RecoveryTests.set
    execute = fixtures.RecoveryTests.execute

    def interrupted(self):
        self.set('cnrt', time='18:00')
        self.clock = fixtures.at('2026-10-21T18:00')
        plan = oneoff.resolve(self.root, 'oneoff', self.config, self.state, [],
                              self.clock, identifier='b' * 32)
        oneoff.claim(self.root, plan, self.clock, '100', self.commit)
        self.clock += timedelta(minutes=96)

    def test_idle_check_schedules_history_reconciliation_without_sources(self):
        self.interrupted()
        output = Path(self.temp.name) / 'outputs.txt'
        # execute deliberately isolates the environment; inject only check outputs.
        original = worker.main
        def check():
            with patch.dict(os.environ, {'FTR_PHASE': 'check', 'GITHUB_OUTPUT': str(output)}):
                return original()
        before = (self.root / oneoff.FILE).read_bytes()
        with patch.object(worker, 'main', side_effect=check):
            self.assertEqual(self.execute(), 0)
        self.assertIn('work=true', output.read_text())
        self.assertIn('cnrt=false', output.read_text())
        self.assertEqual((self.root / oneoff.FILE).read_bytes(), before)
        self.assertFalse(self.reads)

    def test_idle_recovery_persists_error_once_without_read_or_publication(self):
        self.interrupted()
        protected = {name: (self.root / name).read_bytes() for name in (
            '_ftr_config.json', '_ftr_estado.json', 'parques/linea36.csv',
            'controlados/linea36.csv', oneoff.WORKFLOW)}
        before = len(self.commits)
        publish = Mock()
        # A failed interrupted execution must never look like an update success.
        self.assertEqual(self.execute(pages=publish), 1)
        publish.assert_not_called()
        saved = oneoff.load(self.root)
        self.assertEqual(saved['history'][-1]['status'], 'error')
        self.assertEqual(saved['last_execution']['cnrt']['status'], 'error')
        self.assertEqual(saved['execution_history'][-1]['status'], 'error')
        self.assertEqual(saved['receipts']['b' * 32]['status'], 'error')
        for row in (saved['history'][-1], saved['last_execution']['cnrt'],
                    saved['execution_history'][-1], saved['receipts']['b' * 32]):
            self.assertNotIn('finished_utc', row)
            self.assertNotIn('read_utc', row)
            self.assertEqual(row['detected_utc'], self.clock.isoformat())
            self.assertEqual(row['timeout_utc'], (self.clock - timedelta(minutes=6)).isoformat())
        self.assertEqual(len(self.commits), before + 1)
        self.assertEqual(self.commits[-1]['paths'], [oneoff.FILE])
        self.assertEqual({name: (self.root / name).read_bytes() for name in protected}, protected)
        self.assertFalse(self.reads)
        self.assertEqual(self.execute(run='102'), 0)
        self.assertEqual(len(self.commits), before + 1)

    def test_recent_claim_is_left_running(self):
        self.interrupted()
        self.clock -= timedelta(minutes=10)
        before = (self.root / oneoff.FILE).read_bytes()
        self.assertEqual(self.execute(), 0)
        self.assertEqual((self.root / oneoff.FILE).read_bytes(), before)
        self.assertFalse(self.reads)

    def test_other_receipt_is_not_changed(self):
        self.interrupted()
        data = oneoff.load(self.root)
        data['receipts']['c' * 32] = dict(status='running', run_id='200',
                                        started_utc=self.clock.isoformat())
        oneoff.recover_interrupted(data, self.clock)
        self.assertEqual(data['receipts']['c' * 32]['status'], 'running')
        self.assertEqual(data['receipts']['b' * 32]['status'], 'error')
