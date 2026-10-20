import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from _ftr_runtime.config import *
from _ftr_runtime.web import update_public
ROOT=Path(__file__).resolve().parents[1]

class ConfigTests(unittest.TestCase):
    def setUp(self):self.c=load(ROOT)
    def test_all_configured(self):self.assertEqual(len(enabled(self.c)),48)
    def test_168_present(self):self.assertEqual(enabled(self.c)[168],2105)
    def test_link_canonical(self):
        c=copy.deepcopy(self.c);c['sheetUrl']+='?usp=sharing';self.assertEqual(clean_config(c),self.c)
    def test_read_not_folder(self):
        c=copy.deepcopy(self.c);c['sheetUrl']='https://drive.google.com/drive/folders/123'
        with self.assertRaises(ValueError):clean_config(c)
    def test_no_untrusted_scheme(self):
        for v in ['javascript:alert(1)','http://docs.google.com/spreadsheets/d/'+'a'*30,'https://docs.google.com.evil.test/spreadsheets/d/'+'a'*30]:
            c=copy.deepcopy(self.c);c['sheetUrl']=v
            with self.assertRaises(ValueError):clean_config(c)
    def test_day_limits(self):
        for v in [0,61,1.1,True,'5']:
            c=copy.deepcopy(self.c);c['drive']['days']=v
            with self.assertRaises(ValueError):clean_config(c)
    def test_duplicate_reject(self):
        c=copy.deepcopy(self.c);c['lines'].append(c['lines'][0])
        with self.assertRaises(ValueError):clean_config(c)
    def test_no_secret_forwarding(self):
        c=copy.deepcopy(self.c);c['token']='secret';self.assertNotIn('token',clean_config(c))
    def test_disabled_excluded(self):
        c=copy.deepcopy(self.c);c['lines'][0]['enabled']=False;self.assertNotIn(2,enabled(c))
    def test_invalid_anchor(self):
        c=copy.deepcopy(self.c);c['anchor']='2026-02-31'
        with self.assertRaises(ValueError):clean_config(c)
    def test_independent_manual(self):
        t=datetime(2026,10,20,1,tzinfo=timezone.utc)
        self.assertEqual(selected(self.c,self.c,{},'drive',t),['drive'])
        self.assertEqual(selected(self.c,self.c,{},'cnrt',t),['cnrt'])
        self.assertEqual(selected(self.c,self.c,{},'all',t),['cnrt','drive'])
    def test_config_schedule_only(self):
        c=copy.deepcopy(self.c);c['drive']['time']='18:00'
        self.assertEqual(selected(c,self.c,{},'config',datetime.now(timezone.utc)),[])
    def test_config_source_requires_only_drive(self):
        c=copy.deepcopy(self.c);c['period']=2027
        self.assertEqual(selected(c,self.c,{},'config',datetime.now(timezone.utc)),['drive'])
    def test_new_line_both(self):
        c=copy.deepcopy(self.c);c['lines'].append(dict(line=36,company=9999,enabled=True))
        self.assertEqual(selected(c,self.c,{},'config',datetime.now(timezone.utc)),['cnrt','drive'])
    def test_five_days_not_month_cron(self):
        c=copy.deepcopy(self.c);c['anchor']='2026-10-29';t=datetime(2026,11,4,1,tzinfo=timezone.utc)
        self.assertIn('2026-11-03T22:00:00',current_slot(c,'cnrt',t))
    def test_manual_satisfies_slot_not_move_calendar(self):
        t=datetime(2026,10,20,0,tzinfo=timezone.utc);s={'drive':{'served_slot':current_slot(self.c,'drive',t)}}
        self.assertFalse(due(self.c,s,'drive',t))
        self.assertTrue(due(self.c,s,'drive',datetime(2026,10,20,20,tzinfo=timezone.utc)))
    def test_cnrt_before_first_hour_not_due(self):
        self.assertFalse(due(self.c,{},'cnrt',datetime(2026,10,20,0,tzinfo=timezone.utc)))
    def test_paused_manual_still_works(self):
        c=copy.deepcopy(self.c);c['drive']['enabled']=False;t=datetime.now(timezone.utc)
        self.assertFalse(due(c,{},'drive',t));self.assertEqual(selected(c,c,{},'drive',t),['drive'])
    def test_one_hour_retry_cooldown(self):
        t=datetime(2026,10,20,21,tzinfo=timezone.utc)
        self.assertFalse(due(self.c,{'drive':{'attempt_utc':t.isoformat()}},'drive',t))

class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for n in ('index.html','linea.html'):(self.root/n).write_bytes((ROOT/n).read_bytes())
        self.c=load(ROOT)
    def tearDown(self):self.tmp.cleanup()
    def test_update_idempotent(self):
        update_public(self.root,self.c);a=(self.root/'index.html').read_bytes();b=(self.root/'linea.html').read_bytes()
        update_public(self.root,self.c)
        self.assertEqual(a,(self.root/'index.html').read_bytes());self.assertEqual(b,(self.root/'linea.html').read_bytes())
    def test_no_reader_regression(self):
        update_public(self.root,self.c);s=(self.root/'linea.html').read_text()
        self.assertNotIn('header: false',s);self.assertIn('header: true',s)
        self.assertIn('copyControlled()',s);self.assertIn('Copiar pendientes',s);self.assertIn('ftr-publica.js',s)
    def test_new_line_rendered(self):
        self.c['lines'].append(dict(line=36,company=9999,enabled=True));update_public(self.root,self.c)
        import re
        nums=json.loads(re.search(r'const lineas = (\[.*?\]);',(self.root/'index.html').read_text())[1])
        self.assertIn(36,nums);self.assertIn(168,nums);self.assertNotIn(75,nums)
    def test_not_unrelated_file(self):
        (self.root/'test.txt').write_text('untouched');update_public(self.root,self.c);self.assertEqual((self.root/'test.txt').read_text(),'untouched')
    def test_reject_unrecognized_html(self):
        (self.root/'index.html').write_text('<html></html>')
        with self.assertRaises(ValueError):update_public(self.root,self.c)

if __name__=='__main__':unittest.main()
