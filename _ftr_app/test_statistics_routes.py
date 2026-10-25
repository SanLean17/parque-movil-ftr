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
            from _ftr_runtime.test_source_pipeline import SourcePipelineTests
            from _ftr_runtime.statistics_archive import encoded,entry
            fixture=SourcePipelineTests();fixture.setUp()
            try:
                fixture.google(fixture.sheets());public=json.loads((fixture.root/'estadisticas_ftr.json').read_bytes());body=encoded(public)
            finally:fixture.tearDown()
            def github(method,path):
                paths.append(path);self.assertEqual(method,'GET')
                if path=='git/ref/heads/main':return {'object':{'sha':'b'*40}}
                if path.startswith('actions/'):return {'workflow_runs':[]}
                value=cfg if '_ftr_config.json' in path else rules.EMPTY if rules.FILE in path else {} if '_ftr_estado.json' in path else dict(version=1,periodos=[entry(public,body)]) if 'indice.json' in path else public
                return {'content':base64.b64encode(encoded(value)).decode()}
            private={'details':{'novedades_sin_clasificar':{'pendientes':[{'expresion':'X12','frecuencia':2,'periodo':2025,'referencias':[{'fila':7}]}]}}}
            with patch.object(server,'app',app),patch.object(server,'DATA',root),patch.object(server,'api',side_effect=github),patch.object(server,'requests') as requests,patch.object(server,'diagnostic_cache',return_value=private):
                requests.get.return_value.status_code=200;requests.get.return_value.content=body
                statistics_admin.install(server);client=app.test_client()
                client.set_cookie(server.COOKIE_NAME,server.SESSION,domain='127.0.0.1')
                self.assertEqual(client.get('/api/statistics-admin',base_url=server.ORIGIN).status_code,403)
                headers={'X-FTR-CSRF':server.CSRF,'Origin':server.ORIGIN}
                response=client.get('/api/statistics-admin?remote=1',base_url=server.ORIGIN,headers=headers)
                self.assertEqual(response.status_code,200);result=response.json
                self.assertEqual(result['pending'][0]['frecuencia'],2)
                self.assertTrue(all(p.endswith('?ref='+'b'*40) for p in paths if p.startswith('contents/')))
                self.assertNotIn('X12',(root/'diccionario_remoto.json').read_text())
                with patch.object(server,'api',side_effect=AssertionError('No red al reabrir')):
                    self.assertEqual(client.get('/api/statistics-admin',base_url=server.ORIGIN,headers=headers).json['remote'],result['remote'])


    def test_preview_uses_protected_records_requires_session_and_does_not_write(self):
        from _ftr_runtime.test_mechanical_review import ReviewTests
        from _ftr_runtime.statistics_archive import encoded
        import hashlib
        fixture=ReviewTests();fixture.setUp()
        try:
            public,report,detail=fixture.build()
            capsule=detail['novedades_sin_clasificar']['revision_mecanica']
            capsule['sha256_archivo']=hashlib.sha256(encoded(public)).hexdigest()
            capsule['sheetUrl']='https://docs.google.com/spreadsheets/d/HISTORICAL_SOURCE_1234567/edit'
            private={'report':report,'details':detail}
            app=Flask('ftr-preview-test');app.before_request(server.secure)
            with tempfile.TemporaryDirectory() as temp,patch.object(server,'app',app),patch.object(server,'DATA',Path(temp)),patch.object(server,'diagnostic_cache',return_value=private),patch.object(server,'api',side_effect=AssertionError('La vista previa no consulta red')):
                remote=dict(dictionary=rules.EMPTY,expected_dictionary=rules.digest(rules.EMPTY),period=2026,
                    statistics={'2025':public},hashes={'2025':capsule['sha256_archivo']})
                server.write_json(Path(temp)/'diccionario_remoto.json',remote)
                before={p.name:p.read_bytes() for p in Path(temp).iterdir()}
                statistics_admin.install(server);client=app.test_client()
                payload=dict(period=2025,reglas=fixture.candidate()['reglas'],expected_dictionary=rules.digest(rules.EMPTY))
                self.assertEqual(client.post('/api/statistics-preview',base_url=server.ORIGIN,json=payload).status_code,403)
                client.set_cookie(server.COOKIE_NAME,server.SESSION,domain='127.0.0.1')
                headers={'X-FTR-CSRF':server.CSRF,'Origin':server.ORIGIN}
                result=client.post('/api/statistics-preview',base_url=server.ORIGIN,headers=headers,json=payload)
                self.assertEqual(result.status_code,200);self.assertEqual(result.json['despues']['sin_clasificar'],2)
                self.assertEqual(result.json['command']['period'],2025)
                self.assertNotIn('AA111AA',json.dumps(result.json['command']))
                stale=client.post('/api/statistics-preview',base_url=server.ORIGIN,headers=headers,json=dict(payload,expected_dictionary='0'*64))
                self.assertEqual(stale.status_code,400)
                missing=client.post('/api/statistics-preview',base_url=server.ORIGIN,headers=headers,json=dict(payload,period=2026))
                self.assertEqual(missing.status_code,400)
                self.assertEqual({p.name:p.read_bytes() for p in Path(temp).iterdir()},before)
        finally:fixture.tearDown()

    def test_preview_verifies_published_recalculation_with_same_source_timestamp(self):
        import copy
        from datetime import date
        from _ftr_runtime.test_mechanical_review import ReviewTests
        from _ftr_runtime.legacy_mechanics import mechanics
        fixture=ReviewTests();fixture.setUp()
        try:
            public,report,detail=fixture.build()
            capsule=detail['novedades_sin_clasificar']['revision_mecanica']
            capsule['motor_revision']=6
            events=[dict(r,fecha=date.fromisoformat(r['fecha'])) for r in capsule['registros']]
            capsule['estadisticas']['anomalias']=mechanics(events,capsule['diccionario'],6)[0]
            before=copy.deepcopy(capsule)
            app=Flask('ftr-baseline-test');app.before_request(server.secure)
            with tempfile.TemporaryDirectory() as temp,patch.object(server,'app',app),patch.object(server,'DATA',Path(temp)),patch.object(server,'diagnostic_cache',return_value={'report':report,'details':detail}),patch.object(server,'api',side_effect=AssertionError('No red')):
                remote=dict(dictionary=rules.EMPTY,expected_dictionary=rules.digest(rules.EMPTY),period=2026,statistics={'2025':public},hashes={})
                server.write_json(Path(temp)/'diccionario_remoto.json',remote)
                statistics_admin.install(server);client=app.test_client();client.set_cookie(server.COOKIE_NAME,server.SESSION,domain='127.0.0.1')
                payload=dict(period=2025,reglas=fixture.candidate()['reglas'],expected_dictionary=rules.digest(rules.EMPTY))
                response=client.post('/api/statistics-preview',base_url=server.ORIGIN,headers={'X-FTR-CSRF':server.CSRF,'Origin':server.ORIGIN},json=payload)
                self.assertEqual(response.status_code,200,response.json)
                self.assertEqual(response.json['motor_antes'],10)
                self.assertEqual(response.json['antes'],public['anomalias'])
                self.assertEqual(capsule,before)
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
