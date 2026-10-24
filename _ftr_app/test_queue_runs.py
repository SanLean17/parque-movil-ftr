import unittest
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit,parse_qs
from _ftr_app.queue_runs import scan,utc
from _ftr_app.agenda_bridge import classify_run

class ScanTests(unittest.TestCase):
    def runset(self,count):
        start=datetime(2026,10,23,20,tzinfo=timezone.utc)
        return [dict(id=n+1,path='.github/workflows/ftr_sincronizar.yml',status='queued',conclusion=None,
            created_at=(start+timedelta(seconds=n)).isoformat(),display_title='FTR · drive · '+format(n+1,'032x')) for n in range(count)]

    def api(self,rows,calls):
        def get(method,path):
            self.assertEqual(method,'GET');calls.append(path)
            query=parse_qs(urlsplit(path).query)
            if 'status' in query:return dict(total_count=0,workflow_runs=[])
            lo,hi=query['created'][0].split('..')
            selected=sorted([r for r in rows if utc(lo)<=utc(r['created_at'])<=utc(hi)],key=lambda r:r['id'],reverse=True)
            page=int(query['page'][0]);return dict(total_count=len(selected),workflow_runs=selected[(page-1)*100:page*100])
        return get

    def test_more_than_three_pages_and_exact_id(self):
        rows=self.runset(351);rows[0]['display_title']='prefix FTR · drive · '+'f'*32
        calls=[];result=scan(self.api(rows,calls),'2026-10-23T17:00:00-03:00',classify_run,utc('2026-10-23T21:00:00Z'))
        self.assertEqual(len([p for p in calls if 'created=' in p]),4);self.assertEqual(len(result),351);self.assertTrue(result.evidence['complete'])
        self.assertEqual(next(r for r in result if r['id']==2)['request_id'],format(2,'032x'))
        self.assertIsNone(next(r for r in result if r['id']==1)['request_id'])

    def test_search_limit_splits_time_windows_without_losing_runs(self):
        rows=self.runset(1205);calls=[]
        result=scan(self.api(rows,calls),'2026-10-23T20:00:00Z',classify_run,utc('2026-10-23T21:00:00Z'))
        self.assertEqual(len(result),1205);self.assertEqual(len({r['id'] for r in result}),1205)
        self.assertTrue(result.evidence['complete']);self.assertGreater(len(calls),12)

    def test_network_failure_on_later_page_is_not_complete(self):
        calls=[];base=self.api(self.runset(351),calls)
        def get(method,path):
            if 'page=3' in path:raise OSError('offline')
            return base(method,path)
        with self.assertRaises(OSError):scan(get,'2026-10-23T20:00:00Z',classify_run,utc('2026-10-23T21:00:00Z'))

    def test_missing_rows_cannot_be_called_a_complete_negative_search(self):
        def get(method,path):return dict(total_count=1,workflow_runs=[])
        with self.assertRaisesRegex(ValueError,'Faltan'):scan(get,'2026-10-23T20:00:00Z',classify_run,utc('2026-10-23T21:00:00Z'))

    def test_success_without_process_evidence_is_not_confirmed(self):
        rows=self.runset(1);rows[0].update(status='completed',conclusion='success',display_title='FTR · dictionary-save · '+'a'*32,path='.github/workflows/ftr_estadisticas_admin.yml')
        base=self.api(rows,[])
        def get(method,path):return dict(total_count=0,jobs=[]) if '/jobs?' in path else base(method,path)
        result=scan(get,'2026-10-23T20:00:00Z',classify_run,utc('2026-10-23T21:00:00Z'))
        self.assertEqual(result[0]['effect'],'unknown')

    def test_older_active_run_is_still_seen_before_dispatch(self):
        row=self.runset(1)[0];row['created_at']='2026-10-23T18:00:00Z'
        def get(method,path):return dict(total_count=1,workflow_runs=[row]) if 'status=queued' in path else dict(total_count=0,workflow_runs=[])
        result=scan(get,'2026-10-23T20:00:00Z',classify_run,utc('2026-10-23T21:00:00Z'))
        self.assertEqual(result[0]['status'],'queued')
