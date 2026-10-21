"""Reloj completo con horas controladas, API y fuentes ficticias."""
import copy
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml
from _ftr_runtime import native_clock as clock, oneoff, agenda
from _ftr_runtime import test_recovery as fixtures
from _ftr_runtime.config import current_slot

ROOT = Path(__file__).resolve().parents[1]
at = fixtures.at


class NativeClockTests(unittest.TestCase):
    setUp = fixtures.RecoveryTests.setUp
    tearDown = fixtures.RecoveryTests.tearDown
    commit = fixtures.RecoveryTests.commit
    set = fixtures.RecoveryTests.set
    pending_drive = fixtures.RecoveryTests.pending_drive
    execute = fixtures.RecoveryTests.execute

    def save(self):
        (self.root / '_ftr_config.json').write_text(json.dumps(self.config))
        (self.root / '_ftr_estado.json').write_text(json.dumps(self.state))

    def api(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == 'GET' and path.startswith('environments/'):
            return dict(protection_rules=[dict(type='wait_timer', wait_timer=int(path.rsplit('-', 1)[-1]))])
        if method == 'GET' and '/runs?' in path:
            return dict(workflow_runs=self.active_rows)
        if method == 'GET' and path.startswith('actions/workflows/'):
            return dict(state='active')
        if method == 'POST' and path == 'actions/workflows/ftr_sincronizar.yml/dispatches' and self.execute_dispatch:
            self.assertEqual(payload['inputs']['action'], 'recovery')
            self.execute(run=str(self.run_counter), created=self.clock.isoformat())
            self.run_counter += 1
        return {}

    def setup_api(self):
        self.calls = []
        self.active_rows = []
        self.execute_dispatch = False
        self.run_counter = 200

    def prepare(self, mode='real', step=0, retry=0):
        return clock.prepare(self.root, self.clock, mode, step, retry, True, self.api)

    def wake(self, prepared, mode='real', step=0):
        return clock.wake(self.root, self.clock, mode, step, True, prepared['armed_utc'],
                          prepared['minutes'], 12345, self.api)

    def event(self, name=clock.CLOCK, mode='real', step=0, retry=0, conclusion='success'):
        return dict(action='completed', workflow_run=dict(path='.github/workflows/' + name,
                    head_repository=dict(full_name=clock.REPO), head_branch='main', event='workflow_dispatch',
                    conclusion=conclusion, display_title=f'FTR · reloj · {mode} · paso {step} · intento {retry}'))

    def test_daily_wait_then_read_and_next_day_without_a_human(self):
        self.setup_api(); self.pending_drive(); self.execute_dispatch = True
        self.clock = at('2026-10-21T16:59')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        prepared = self.prepare()
        self.assertEqual(prepared['minutes'], 1)
        self.assertEqual(self.reads, [])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.clock += timedelta(minutes=1, seconds=8)
        self.assertEqual(self.wake(prepared)['status'], 'coordinator_requested')
        self.assertEqual(self.reads, ['drive'])
        next_plan = clock.snapshot(self.root, self.clock)
        self.assertEqual(clock.instant(next_plan['next_due_utc']), at('2026-10-22T17:00'))
        result = clock.rearm(self.root, self.event(clock.COORDINATOR), self.clock, True, self.api)
        self.assertEqual(result['status'], 'next_wait_requested')
        self.assertEqual(self.calls[-1][2]['inputs'], dict(mode='real', step='0', retry='0'))

    def test_before_deadline_only_rearms_without_reading(self):
        self.setup_api(); self.pending_drive(); self.clock = at('2026-10-21T16:20')
        prepared = self.prepare(); self.assertEqual(prepared['minutes'], 15)
        self.clock += timedelta(minutes=15, seconds=10)
        self.assertEqual(self.wake(prepared)['status'], 'waiting_for_deadline')
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))

    def test_changed_hour_is_reloaded_after_wait_not_taken_from_old_plan(self):
        self.setup_api(); self.pending_drive(); self.clock = at('2026-10-21T16:59')
        prepared = self.prepare()
        self.config['drive']['time'] = '19:00'
        self.state['drive']['schedule_effective_from_utc'] = self.clock.isoformat(); self.save()
        self.clock += timedelta(minutes=2)
        self.assertEqual(self.wake(prepared)['status'], 'waiting_for_deadline')
        self.assertEqual(clock.instant(clock.snapshot(self.root, self.clock)['next_due_utc']), at('2026-10-21T19:00'))
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))

    def test_disabled_sources_stop_and_cancel_only_clock_waiters(self):
        self.setup_api()
        for key in ('drive', 'cnrt'): self.config[key]['enabled'] = False
        self.save()
        self.assertIsNone(clock.snapshot(self.root, self.clock))
        self.active_rows = [dict(id=1, status='waiting', display_title='FTR · reloj · real · paso 0 · intento 0'),
                            dict(id=2, status='waiting', display_title='FTR · reloj · prueba · paso 0 · intento 0'),
                            dict(id=3, status='in_progress', display_title='FTR · recovery · automático')]
        result = clock.rearm(self.root, self.event(clock.COORDINATOR), self.clock, True, self.api)
        self.assertEqual(result['status'], 'idle')
        self.assertEqual([x[1] for x in self.calls if x[0] == 'POST'], ['actions/runs/1/cancel'])

    def test_cancel_oneoff_while_waiting_cannot_read_old_appointment(self):
        self.setup_api(); self.clock = at('2026-10-21T17:45')
        identifier = self.set('cnrt', time='17:46')
        prepared = self.prepare(); self.assertEqual(prepared['minutes'], 1)
        oneoff.apply_command(self.root, 'oneoff-cancel', dict(source='cnrt', expected_id=identifier),
                             'f' * 32, self.clock, self.commit)
        self.clock += timedelta(minutes=1, seconds=6)
        self.assertEqual(self.wake(prepared)['status'], 'waiting_for_deadline')
        self.assertEqual(self.reads, [])

    def test_recurrent_and_oneoff_same_time_then_duplicate_are_one_read(self):
        self.setup_api(); self.pending_drive(); self.execute_dispatch = True
        self.clock = at('2026-10-21T16:59'); self.set('drive', time='17:00')
        prepared = self.prepare(); self.clock += timedelta(minutes=1, seconds=7)
        self.wake(prepared); self.wake(prepared)
        self.assertEqual(self.reads, ['drive'])
        self.assertFalse(oneoff.load(self.root)['pending'])

    def test_five_day_cnrt_does_not_become_daily_or_move_at_month_boundary(self):
        self.setup_api(); self.config['drive']['enabled'] = False
        self.config['anchor'] = '2026-12-29'; self.config['cnrt']['days'] = 5
        start = at('2026-12-29T22:00'); self.clock = start + timedelta(minutes=1)
        self.state['cnrt'] = dict(status='success', read_utc=start.isoformat(),
                                  served_slot=current_slot(self.config, 'cnrt', start)); self.save()
        self.assertEqual(clock.instant(clock.snapshot(self.root, self.clock)['next_due_utc']), at('2027-01-03T22:00'))
        self.assertIn(self.prepare()['minutes'], clock.MINUTES)

    def test_60_day_frequency_and_366_day_oneoff_use_bounded_waits(self):
        self.setup_api(); self.config['drive']['enabled'] = False
        self.config['cnrt']['days'] = 60
        self.state['cnrt']['served_slot'] = current_slot(self.config, 'cnrt', self.clock); self.save()
        self.assertEqual(self.prepare()['minutes'], 10080)
        self.config['cnrt']['enabled'] = False; self.save()
        extra = oneoff.load(self.root)
        extra['pending']['drive'] = dict(id='a'*32, source='drive', at=(self.clock + timedelta(days=366)).isoformat())
        (self.root / oneoff.FILE).write_text(json.dumps(extra))
        self.assertEqual(self.prepare()['minutes'], 10080)

    def test_source_error_waits_an_hour_and_keeps_old_data(self):
        self.setup_api(); self.pending_drive(); self.execute_dispatch = True; self.failing.add('drive')
        before = (self.root / 'controlados/linea36.csv').read_bytes()
        self.clock = at('2026-10-21T16:59'); prepared = self.prepare()
        self.clock += timedelta(minutes=1); self.wake(prepared)
        self.assertEqual((self.root / 'controlados/linea36.csv').read_bytes(), before)
        self.assertEqual(clock.instant(clock.snapshot(self.root, self.clock)['next_due_utc']), at('2026-10-21T18:00'))
        self.assertEqual(self.reads, ['drive'])

    def test_failed_publication_is_retried_without_reading_again(self):
        self.setup_api(); self.pending_drive(); self.clock = at('2026-10-21T17:00')
        self.assertEqual(self.execute(pages=ValueError('Falla simulada')), 1)
        self.execute_dispatch = True
        prepared = self.prepare(); self.assertEqual(prepared['minutes'], 15)
        self.clock += timedelta(minutes=15, seconds=7); self.wake(prepared)
        self.assertEqual(self.reads, ['drive'])
        self.assertEqual(json.loads((self.root / '_ftr_estado.json').read_text())['publication']['status'], 'success')

    def test_busy_coordinator_is_not_cancelled_or_started_twice(self):
        self.setup_api(); self.pending_drive(); self.clock = at('2026-10-21T17:00')
        self.active_rows = [dict(path='.github/workflows/ftr_sincronizar.yml', status='in_progress')]
        prepared = self.prepare(); self.assertEqual(prepared['minutes'], 5)
        self.clock += timedelta(minutes=5, seconds=6)
        self.assertEqual(self.wake(prepared)['status'], 'coordinator_busy')
        self.assertFalse(any(x[0] == 'POST' for x in self.calls))

    def test_cancelled_claim_waits_for_timeout_then_recovers_once(self):
        self.setup_api(); self.pending_drive(); self.clock = at('2026-10-21T17:00')
        plan = oneoff.resolve(self.root, 'recovery', self.config, self.state, ['drive'], self.clock)
        oneoff.claim(self.root, plan, self.clock, '101', self.commit)
        self.assertEqual(clock.instant(clock.snapshot(self.root, self.clock)['next_due_utc']), self.clock + timedelta(minutes=95, seconds=1))
        self.clock += timedelta(minutes=96); self.execute_dispatch = True
        prepared = self.prepare(); self.clock += timedelta(minutes=1, seconds=5); self.wake(prepared)
        self.assertEqual(self.reads, ['drive'])

    def test_proof_four_cycles_rearms_and_stops_without_any_source_dispatch(self):
        self.setup_api()
        for step in range(4):
            prepared = self.prepare('prueba', step)
            self.clock += timedelta(minutes=1, seconds=8)
            result = self.wake(prepared, 'prueba', step)
            self.assertEqual(result['status'], 'proof_complete')
            result = clock.renew(self.root, self.clock, 'prueba', step, 0, False, 'success', 'success', self.api)
            self.assertEqual(result['status'], 'next_wait_requested' if step < 3 else 'no_rearm')
        self.assertEqual(self.reads, [])
        self.assertEqual(len([x for x in self.calls if x[0] == 'POST']), 3)
        self.assertTrue(all(x[1] == 'actions/workflows/' + clock.CLOCK + '/dispatches' for x in self.calls if x[0] == 'POST'))

    def test_no_early_wake_even_if_wait_timer_bypassed(self):
        self.setup_api(); prepared = self.prepare('prueba'); self.clock += timedelta(seconds=59)
        with self.assertRaisesRegex(ValueError, 'No se cumplió'): self.wake(prepared, 'prueba')
        self.assertFalse(any(x[0] == 'POST' for x in self.calls))

    def test_environment_absent_wrong_or_requires_approval_fails_closed(self):
        for rules in ([], [dict(type='wait_timer', wait_timer=0)],
                      [dict(type='wait_timer', wait_timer=1), dict(type='required_reviewers')]):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                clock.validate_wait(lambda *args: dict(protection_rules=rules), 1)

    def test_foreign_repo_branch_pr_ci_and_replaced_waits_cannot_rearm(self):
        event = self.event(clock.COORDINATOR)
        variants = []
        for key, value in [('head_branch', 'feature'), ('head_repository', {'full_name': 'other/fork'}),
                           ('event', 'pull_request'), ('event', 'push'), ('path', '.github/workflows/ftr_auditoria_ci.yml'),
                           ('path', '.github/workflows/ftr_reloj_nativo.yml')]:
            row = copy.deepcopy(event); row['workflow_run'][key] = value; variants.append(row)
        for row in variants:
            self.assertIsNone(clock.follow_up(row))

    def test_failed_wait_retries_are_bounded_and_have_backoff(self):
        for retry, delay in enumerate((0, 5, 15, 60)):
            follow = clock.next_cycle('real', 0, retry, 'failure')
            self.assertEqual(follow['retry'] if follow else None, str(retry+1) if retry < 3 else None)
            self.assertEqual(clock.choose_wait(self.clock, self.clock, retry), delay or 1)

    def test_disabled_flag_does_not_start_production_but_allows_proof(self):
        self.setup_api()
        self.assertEqual(clock.prepare(self.root, self.clock, 'real', 0, 0, False, self.api)['status'], 'disabled')
        self.assertEqual(clock.rearm(self.root, self.event(clock.COORDINATOR), self.clock, False, self.api)['status'], 'disabled')
        self.assertFalse(self.calls)

    def test_arbitrary_dispatch_destinations_rejected(self):
        self.setup_api()
        with self.assertRaises(ValueError): clock.dispatch(self.api, 'other.yml', {})
        self.assertFalse(self.calls)

    def test_webhook_without_path_uses_verified_run_not_a_guessed_workflow(self):
        self.setup_api()
        event = self.event(clock.COORDINATOR)
        verified = dict(event['workflow_run'], status='completed', id=555)
        event['workflow_run'].pop('path'); event['workflow_run']['id'] = 555
        def call(method, path, payload=None):
            if path == 'actions/runs/555': return verified
            return self.api(method, path, payload)
        self.assertEqual(clock.rearm(self.root, event, self.clock, True, call)['status'], 'next_wait_requested')
        verified['status'] = 'in_progress'
        self.assertEqual(clock.rearm(self.root, event, self.clock, False, call)['status'], 'event_not_completed')

    def test_direct_renewal_ignores_replaced_idle_and_disabled_cycles(self):
        self.setup_api()
        for preparation, awakening in [('success', 'cancelled'), ('cancelled', 'skipped'),
                                        ('success', 'skipped'), ('skipped', 'skipped')]:
            self.assertEqual(clock.renew(self.root, self.clock, 'real', 0, 0, True,
                             preparation, awakening, self.api)['status'], 'no_rearm')
        self.assertEqual(clock.renew(self.root, self.clock, 'real', 0, 0, False,
                         'success', 'success', self.api)['status'], 'disabled')
        self.assertFalse(self.calls)

    def test_direct_renewal_retries_a_failed_cycle_and_stops_at_limit(self):
        self.setup_api()
        result = clock.renew(self.root, self.clock, 'real', 0, 0, True, 'failure', 'skipped', self.api)
        self.assertEqual(result['retry'], '1')
        self.assertEqual(clock.renew(self.root, self.clock, 'real', 0, 3, True,
                         'success', 'failure', self.api)['status'], 'no_rearm')
        self.assertEqual(clock.renew(self.root, self.clock, 'prueba', 0, 0, False,
                         'success', 'failure', self.api)['status'], 'no_rearm')

    def test_late_clock_completion_webhook_cannot_create_a_second_chain(self):
        self.setup_api()
        self.assertEqual(clock.rearm(self.root, self.event(), self.clock, True, self.api)['status'], 'no_rearm')
        self.assertFalse(self.calls)

    def test_native_workflows_have_no_sources_push_or_schedule_and_main_only(self):
        docs = {name: yaml.load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
                for name in (clock.CLOCK, clock.REARM)}
        self.assertEqual(set(docs[clock.CLOCK]['on']), {'workflow_dispatch'})
        self.assertEqual(set(docs[clock.REARM]['on']), {'workflow_run'})
        self.assertNotIn('FTR - Reloj automático', docs[clock.REARM]['on']['workflow_run']['workflows'])
        self.assertNotIn('concurrency', docs[clock.CLOCK])
        self.assertEqual(docs[clock.CLOCK]['jobs']['despertar']['concurrency']['cancel-in-progress'], 'true')
        self.assertNotIn('concurrency', docs[clock.CLOCK]['jobs']['renovar'])
        self.assertEqual(docs[clock.CLOCK]['jobs']['renovar']['needs'], ['preparar', 'despertar'])
        self.assertEqual(docs[clock.CLOCK]['jobs']['despertar']['environment']['deployment'], 'false')
        for doc in docs.values():
            self.assertEqual(doc['permissions']['contents'], 'read')
            for job in doc['jobs'].values():
                for step in job['steps']:
                    self.assertNotIn('GOOGLE_SERVICE_ACCOUNT_JSON', json.dumps(step))
                    if step.get('uses', '').startswith('actions/checkout'):
                        self.assertEqual(step['with'], {'ref': 'main', 'persist-credentials': 'false'})
        child = yaml.load((ROOT / '.github/workflows/ftr_sincronizar.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        self.assertEqual(child['concurrency']['cancel-in-progress'], 'false')
        self.assertEqual(child['concurrency']['queue'], 'max')


if __name__ == '__main__': unittest.main()
