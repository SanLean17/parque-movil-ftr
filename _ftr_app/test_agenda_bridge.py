import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import agenda_bridge as bridge


def run(status='completed',conclusion='success',title='FTR · schedule · automático'):
    return dict(id=1,status=status,conclusion=conclusion,display_title=title,html_url='https://github.com/a/b/actions/runs/1',created_at='2026-10-20T20:00:00Z',updated_at='2026-10-20T20:00:10Z',run_attempt=1)
def jobs(process='skipped'):
    return [{'steps':[{'name':'Comprobar agenda o solicitud','conclusion':'success'},{'name':'Procesar, validar, guardar y publicar','conclusion':process}]}]

class RunStateTests(unittest.TestCase):
    def setUp(self):bridge._cache.clear()
    def test_skipped_is_not_updated(self):self.assertEqual(bridge.classify_run(run(),jobs())['effect'],'agenda_only')
    def test_processed_is_updated(self):self.assertEqual(bridge.classify_run(run(),jobs('success'))['effect'],'updated')
    def test_config_not_claimed_as_read(self):self.assertEqual(bridge.classify_run(run(title='FTR · config · 123'),jobs('success'))['effect'],'configuration')
    def test_diagnostic_not_published(self):self.assertEqual(bridge.classify_run(run(title='FTR · diagnostic · 123'),jobs('success'))['effect'],'diagnostic')
    def test_failed_never_updated(self):self.assertEqual(bridge.classify_run(run(conclusion='failure'),jobs('success'))['effect'],'failed')
    def test_no_steps_not_assumed_success(self):self.assertEqual(bridge.classify_run(run(),[])['effect'],'unknown')
    def test_running(self):self.assertEqual(bridge.classify_run(run(status='in_progress',conclusion=None),[])['effect'],'running')
    def test_completed_jobs_cached(self):
        def call(method,path):return {'workflow_runs':[run()]} if '/runs?' in path else {'jobs':jobs()}
        with patch.object(bridge.server,'api',side_effect=call) as api:
            self.assertEqual(bridge.last_runs()[0]['effect'],'agenda_only')
            bridge.last_runs();self.assertEqual(api.call_count,7)
    def test_retry_not_reuse_old_result(self):
        r=run()
        with patch.object(bridge.server,'api',side_effect=[{'workflow_runs':[r]},{'workflow_runs':[]},{'workflow_runs':[]},{'jobs':jobs()},{'workflow_runs':[{**r,'run_attempt':2}]},{'workflow_runs':[]},{'workflow_runs':[]},{'jobs':jobs('success')}]):
            self.assertEqual(bridge.last_runs()[0]['effect'],'agenda_only')
            self.assertEqual(bridge.last_runs()[0]['effect'],'updated')
    def test_permission_problem_not_success(self):
        with patch.object(bridge.server,'api',side_effect=[{'workflow_runs':[run()]},{'workflow_runs':[]},{'workflow_runs':[]},ValueError('denied')]):
            self.assertEqual(bridge.last_runs()[0]['effect'],'unknown')

class BothEntrancesTests(unittest.TestCase):
    def setUp(self):bridge._cache.clear()
    def test_legacy_scheduled_execution_visible(self):
        r={**run(),'id':2,'event':'schedule'}
        with patch.object(bridge.server,'api',side_effect=[{'workflow_runs':[]},{'workflow_runs':[r]},{'workflow_runs':[]},{'jobs':jobs('success')}]) as api:
            out=bridge.last_runs()
        self.assertEqual(out[0]['id'],2);self.assertEqual(out[0]['effect'],'updated')
        self.assertIn('actualizar_parques.yml',api.call_args_list[1].args[1])
    def test_same_run_not_shown_twice(self):
        r=run()
        with patch.object(bridge.server,'api',side_effect=[{'workflow_runs':[r]},{'workflow_runs':[r]},{'workflow_runs':[]},{'jobs':jobs()}]):
            self.assertEqual(len(bridge.last_runs()),1)
    def test_scheduled_running_blocks_duplicate_submit(self):
        r={**run(status='in_progress',conclusion=None),'event':'schedule'}
        with patch.object(bridge.server,'api',side_effect=[{'workflow_runs':[]},{'workflow_runs':[r]},{'workflow_runs':[]}]):
            self.assertEqual(bridge.last_runs()[0]['status'],'in_progress')

if __name__=='__main__':unittest.main()
