"""Publicar configuración hasta CSV/HTML/estado; fuentes y Git remotos simulados."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import actualizar_parques as parks
from _ftr_runtime import worker
from _ftr_runtime.config import load, digest, enabled
from _ftr_tools import ejecutar as entry
from _ftr_runtime.test_source_pipeline import admin

REPO=Path(__file__).resolve().parents[1]


class ConfigTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        self.config=load(REPO)
        self.config['lines']=[dict(line=36,company=9999,enabled=True)]
        self.clock=datetime(2026,10,21,20,1,tzinfo=timezone.utc)
        self.tables=[];self.downloads=[]
        for folder in ('parques','controlados','_ftr_admin'):(self.root/folder).mkdir()
        for name in ('index.html','linea.html','ftr-publica.js','ftr-datos.js','ftr-historial.js','ftr-historial-publico.js','scraper.py','actualizar_parques.py','_ftr_admin/diagnostico_publica.pem'):
            shutil.copy2(REPO/name,self.root/name)
        (self.root/'_ftr_config.json').write_text(json.dumps(self.config))
        (self.root/'_ftr_estado.json').write_text('{}')
        (self.root/'parques/linea36.csv').write_text('dominio,interno,linea,empresaNro\nAA111AA,1,36,9999\n')
        (self.root/'controlados/linea36.csv').write_text('linea,fecha,dominio,interno\n36,01/01/2026,ZZ999ZZ,9\n')

    def tearDown(self):self.temp.cleanup()

    def fake_cnrt(self,args,cwd,**kwargs):
        work=Path(cwd);mapping={}
        exec((work/'configuracion_lineas.py').read_text(),mapping)
        if Path(args[1]).name=='scraper.py':
            (work/'cnrt').mkdir()
            for company in mapping['EMPRESAS_CNRT']:
                self.downloads.append(company)
                rows='dominio,interno,linea,empresaNro\n'
                for number,c in mapping['LINEAS_EMPRESAS'].items():
                    if company==c:rows+=f'AA111AA,1,{number},{c}\n'
                (work/'cnrt'/f'empresa_{company}.csv').write_text(rows)
        else:
            with patch.object(parks,'CARPETA_CNRT',work/'cnrt'),patch.object(parks,'CARPETA_PARQUES',work/'parques'),patch.object(parks,'LINEAS_EMPRESAS',mapping['LINEAS_EMPRESAS']):
                parks.procesar()
        return subprocess.CompletedProcess(args,0)

    def execute(self, candidate, denied=False):
        tables=[admin.base.Sheet(f'LINEA {number}',{(1,1):'FECHA',(1,2):'DOMINIO',(1,3):'INTERNO',
                 **({(2,1):'20/10/2026',(2,2):'AA111AA',(2,3):1} if candidate['period']==2026 else {})}) for number in enabled(candidate)]
        with ExitStack() as stack:
            system={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR','SYSTEMDRIVE','TEMP','TMP')}
            stack.enter_context(patch.dict(os.environ,dict(system,FTR_ACTION='config',FTR_CONFIG=json.dumps(candidate),FTR_EXPECTED=digest(load(self.root)),GITHUB_REF='refs/heads/main',GITHUB_REPOSITORY='SanLean17/parque-movil-ftr'),clear=True))
            stack.enter_context(patch.object(worker,'ROOT',self.root))
            stack.enter_context(patch.object(worker,'REPORT_DIR',Path(self.temp.name)/'reports'))
            stack.enter_context(patch.object(worker,'now',return_value=self.clock))
            for name in ('plan','selected','commit'):stack.enter_context(patch.object(worker,name,getattr(worker,name)))
            stack.enter_context(patch.object(entry.native_schedule,'preflight'))
            self.commit=stack.enter_context(patch.object(entry,'commit_validated',return_value='FICTITIOUS_COMMIT'))
            self.pages=stack.enter_context(patch.object(worker,'build_pages'))
            stack.enter_context(patch.object(worker.subprocess,'run',side_effect=self.fake_cnrt))
            self.export=stack.enter_context(patch.object(admin.base,'export_sheet',side_effect=admin.base.DiagnosisError('Google rechazó la lectura (403).') if denied else None,return_value=b'FAKE_XLSX'))
            stack.enter_context(patch.object(admin.base,'decode_xlsx',return_value=tables))
            return entry.main()

    def test_new_line_new_company_no_existing_csv(self):
        candidate=copy.deepcopy(self.config)
        candidate['lines'].append(dict(line=998,company=8888,enabled=True))
        self.assertFalse((self.root/'parques/linea998.csv').exists())
        self.assertEqual(self.execute(candidate),0)
        self.assertIn(8888,self.downloads)
        self.assertIn('AA111AA',(self.root/'parques/linea998.csv').read_text())
        self.assertIn('998,20/10/2026,AA111AA',(self.root/'controlados/linea998.csv').read_text(encoding='utf-8-sig'))
        self.assertIn('const lineas = [36, 998];',(self.root/'index.html').read_text(encoding='utf-8'))
        history=json.loads((self.root/'historial/linea998.json').read_text(encoding='utf-8'))
        self.assertEqual(history['controles'],[dict(dominio='AA111AA',fecha='2026-10-20',interno='1')])
        manifest=json.loads((self.root/'ftr_publicacion.json').read_text())
        for name in ('historial/linea998.json','historial/linea36.json','ftr-historial.js','ftr-historial-publico.js'):
            self.assertIn(name,manifest['files_sha256'])
        self.assertIn('historial/linea998.json',self.commit.call_args_list[0].args[1])
        self.assertEqual(self.commit.call_count,2);self.pages.assert_called_once()
        self.assertEqual(self.commit.call_args.args[1],['_ftr_estado.json'])

    def test_shared_company_downloaded_once(self):
        candidate=copy.deepcopy(self.config)
        candidate['lines'].append(dict(line=998,company=9999,enabled=True))
        self.assertEqual(self.execute(candidate),0)
        self.assertEqual(self.downloads,[9999])
        self.assertNotIn(',36,9999',(self.root/'parques/linea998.csv').read_text())

    def test_new_source_replaces_controls_same_year(self):
        candidate=copy.deepcopy(self.config)
        candidate['sheetUrl']='https://docs.google.com/spreadsheets/d/NEW_TEST_SOURCE_1234567890/edit'
        self.assertEqual(self.execute(candidate),0)
        self.export.assert_called_once_with('NEW_TEST_SOURCE_1234567890')
        data=(self.root/'controlados/linea36.csv').read_text(encoding='utf-8-sig')
        self.assertIn('AA111AA',data);self.assertNotIn('ZZ999ZZ',data)
        self.assertEqual(self.downloads,[])

    def test_denied_source_preserves_old_config_state_and_csv(self):
        candidate=copy.deepcopy(self.config)
        candidate['sheetUrl']='https://docs.google.com/spreadsheets/d/DENIED_TEST_SOURCE_1234567890/edit'
        paths=['_ftr_config.json','_ftr_estado.json','controlados/linea36.csv','parques/linea36.csv']
        before={p:(self.root/p).read_bytes() for p in paths}
        self.assertEqual(self.execute(candidate,denied=True),1)
        self.assertEqual(before,{p:(self.root/p).read_bytes() for p in paths})
        self.commit.assert_not_called();self.pages.assert_not_called()

    def test_valid_empty_new_period_is_published_as_empty(self):
        candidate=copy.deepcopy(self.config);candidate['period']=2027
        candidate['sheetUrl']='https://docs.google.com/spreadsheets/d/'+'y'*30+'/edit'
        self.assertEqual(self.execute(candidate),0)
        self.assertEqual((self.root/'controlados/linea36.csv').read_text(encoding='utf-8-sig'),'linea,fecha,dominio,interno\n')
        self.assertEqual(json.loads((self.root/'_ftr_estado.json').read_text())['drive']['records'],0)
        self.assertEqual(json.loads((self.root/'historial/linea36.json').read_text())['controles'],[])

    def test_new_period_requires_new_source_and_preserves_previous(self):
        candidate=copy.deepcopy(self.config);candidate['period']=2027
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.execute(candidate),1)
        for p,body in before.items():self.assertEqual(p.read_bytes(),body,p)
        self.commit.assert_not_called();self.pages.assert_not_called()

    def test_disable_reactivate_keeps_prior_line_files(self):
        candidate=copy.deepcopy(self.config)
        candidate['lines'].append(dict(line=998,company=9999,enabled=True))
        self.assertEqual(self.execute(candidate),0)
        before=(self.root/'controlados/linea998.csv').read_bytes()
        history=(self.root/'historial/linea998.json').read_bytes()
        candidate['lines'][1]['enabled']=False
        self.assertEqual(self.execute(candidate),0)
        self.assertEqual((self.root/'controlados/linea998.csv').read_bytes(),before)
        self.assertEqual((self.root/'historial/linea998.json').read_bytes(),history)
        self.assertIn('const lineas = [36];',(self.root/'index.html').read_text(encoding='utf-8'))
        candidate['lines'][1]['enabled']=True
        self.assertEqual(self.execute(candidate),0)
        self.assertIn('const lineas = [36, 998];',(self.root/'index.html').read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
