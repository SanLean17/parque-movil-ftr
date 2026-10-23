import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from _ftr_app import server,statistics_admin
from _ftr_runtime import dictionary_rules as rules
from _ftr_runtime.config import load

class StatisticsRoutesTests(unittest.TestCase):
    def test_remote_snapshot_is_pinned_private_details_stay_local_and_cache_reopens(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);app=Flask('ftr-statistics-test');app.before_request(server.secure)
            cfg=load(Path(__file__).resolve().parents[1]);paths=[]
            def github(method,path):
                paths.append(path);self.assertEqual(method,'GET')
                if path=='git/ref/heads/main':return {'object':{'sha':'b'*40}}
                if path.startswith('actions/'):return {'workflow_runs':[]}
                value=cfg if '_ftr_config.json' in path else rules.EMPTY if rules.FILE in path else {'periodos':[{'periodo':2026}]}
                return {'content':base64.b64encode(json.dumps(value).encode()).decode()}
            private={'details':{'novedades_sin_clasificar':{'pendientes':[{'expresion':'X12','frecuencia':2,'periodo':2025,'referencias':[{'fila':7}]}]}}}
            with patch.object(server,'app',app),patch.object(server,'DATA',root),patch.object(server,'api',side_effect=github),patch.object(server,'diagnostic_cache',return_value=private):
                statistics_admin.install(server);client=app.test_client()
                client.set_cookie(server.COOKIE_NAME,server.SESSION,domain='127.0.0.1')
                self.assertEqual(client.get('/api/statistics-admin',base_url=server.ORIGIN).status_code,403)
                headers={'X-FTR-CSRF':server.CSRF}
                response=client.get('/api/statistics-admin?remote=1',base_url=server.ORIGIN,headers=headers)
                self.assertEqual(response.status_code,200);result=response.json
                self.assertEqual(result['pending'][0]['frecuencia'],2)
                self.assertTrue(all(p.endswith('?ref='+'b'*40) for p in paths if p.startswith('contents/')))
                self.assertNotIn('X12',(root/'diccionario_remoto.json').read_text())
                with patch.object(server,'api',side_effect=AssertionError('No red al reabrir')):
                    self.assertEqual(client.get('/api/statistics-admin',base_url=server.ORIGIN,headers=headers).json['remote'],result['remote'])

if __name__=='__main__':unittest.main()
