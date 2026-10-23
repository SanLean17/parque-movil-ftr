import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from cryptography.fernet import Fernet
from _ftr_app import server,statistics_admin
from _ftr_app.private_interpretations import Store
from _ftr_runtime import dictionary_rules as rules,record_interpretation as records
from _ftr_runtime import test_mechanical_review as fixtures
WINDOWS_PROTECT=server.protect

class ParticularTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.temp=self.stack.enter_context(tempfile.TemporaryDirectory());self.root=Path(self.temp)
        fixture=fixtures.ReviewTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        public,report,detail=fixture.build();self.report=dict(report=report,details=detail)
        self.events=detail['novedades_sin_clasificar']['revision_mecanica']['registros']
        self.remote=dict(dictionary=rules.EMPTY,expected_dictionary=rules.digest(rules.EMPTY),period=2026,statistics={'2025':public})
        app=Flask('private-test');app.before_request(server.secure)
        cipher=Fernet(Fernet.generate_key())
        for name,value in [('app',app),('DATA',self.root),('protect',lambda data,decrypt=False:cipher.decrypt(data) if decrypt else cipher.encrypt(data)),('diagnostic_cache',lambda:self.report),('api',lambda *a:(_ for _ in ()).throw(AssertionError('Sin red')))]:self.stack.enter_context(patch.object(server,name,value))
        server.write_json(self.root/'diccionario_remoto.json',self.remote)
        statistics_admin.install(server);self.client=app.test_client();self.client.set_cookie(server.COOKIE_NAME,server.SESSION,domain='127.0.0.1')
        self.headers={'X-FTR-CSRF':server.CSRF,'Origin':server.ORIGIN}
        event=self.events[1];self.body=dict(period=2025,registro_id=records.reference(event)['registro_id'],fragmentos=records.suggestions(event['novedades'],rules.EMPTY),regla=dict(expresion='JGO B LARGA',categoria='direccion',componente='barra_larga',habilitada=True))
    def post(self,path,body):return self.client.post('/api/'+path,base_url=server.ORIGIN,headers=self.headers,json=body)
    def test_store_uses_final_profile_selected_at_startup(self):
        store=Store(server)
        with tempfile.TemporaryDirectory() as directory,patch.object(server,'DATA',Path(directory)):
            self.assertEqual(store.path,Path(directory)/'interpretaciones.dpapi')
            self.assertEqual(store.read()['registros'],{})
    def test_preview_cancel_save_reopen_and_no_public_queue_or_plaintext(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        record=self.post('dictionary-record',dict(period=2025,registro_id=self.body['registro_id']))
        self.assertEqual(record.status_code,200);self.assertEqual(record.json['registro']['novedades_original'],'JGO B LARGA')
        response=self.post('dictionary-record-preview',self.body);self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(len(response.json['afectados']),1)
        self.assertEqual({p.name:p.read_bytes() for p in self.root.iterdir()},before)
        receipt=dict(confirmation=response.json['confirmation'])
        saved=self.post('dictionary-record-save',receipt);self.assertEqual(saved.status_code,200,saved.json)
        self.assertFalse(saved.json['publicacion_verificada'])
        self.assertNotIn(b'JGO B LARGA',(self.root/'interpretaciones.dpapi').read_bytes())
        self.assertNotIn(b'AA111AA',(self.root/'interpretaciones.dpapi').read_bytes())
        self.assertEqual(len(Store(server).read()['registros']),1)
        self.assertEqual(self.post('dictionary-record-save',receipt).status_code,400)
        reopened=self.post('dictionary-record',dict(period=2025,registro_id=self.body['registro_id']))
        self.assertTrue(reopened.json['guardada']);self.assertEqual(reopened.json['analisis']['pendientes'],[])
        self.assertEqual(set(p.name for p in self.root.iterdir()),{'diccionario_remoto.json','interpretaciones.dpapi'})
    def test_stale_preview_and_expiration_block_writes(self):
        response=self.post('dictionary-record-preview',self.body)
        self.remote['dictionary']=dict(rules.EMPTY,revision=2);server.write_json(self.root/'diccionario_remoto.json',self.remote)
        self.assertEqual(self.post('dictionary-record-save',dict(confirmation=response.json['confirmation'])).status_code,400)
        response=self.post('dictionary-record-preview',self.body)
        with patch('time.monotonic',return_value=10**15):self.assertEqual(self.post('dictionary-record-save',dict(confirmation=response.json['confirmation'])).status_code,400)
        self.assertFalse((self.root/'interpretaciones.dpapi').exists())
    def test_no_auth_tampering_or_plaintext_fallback(self):
        for route in ('dictionary-record','dictionary-records','dictionary-record-preview','dictionary-record-save'):
            self.assertEqual(self.client.post('/api/'+route,base_url=server.ORIGIN,json=self.body).status_code,403)
        invalid=dict(self.body,fragmentos=[dict(self.body['fragmentos'][0],fin=99999)])
        self.assertEqual(self.post('dictionary-record-preview',invalid).status_code,400)
        response=self.post('dictionary-record-preview',self.body)
        with patch.object(server,'protect',side_effect=ValueError('Protección no disponible')):
            self.assertEqual(self.post('dictionary-record-save',dict(confirmation=response.json['confirmation'])).status_code,400)
        self.assertFalse((self.root/'interpretaciones.dpapi').exists())
    @unittest.skipUnless(os.name=='nt','DPAPI pertenece a Windows; el resto del contrato también se prueba en Linux.')
    def test_real_windows_dpapi_reopens_from_same_user_profile(self):
        with patch.object(server,'protect',WINDOWS_PROTECT):
            response=self.post('dictionary-record-preview',self.body)
            result=self.post('dictionary-record-save',dict(confirmation=response.json['confirmation']))
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(len(Store(server).read()['registros']),1)
            self.assertNotIn(b'JGO B LARGA',(self.root/'interpretaciones.dpapi').read_bytes())
