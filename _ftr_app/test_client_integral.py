import base64
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import server
import main0631
from _ftr_runtime.config import load, digest


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.config=load(Path(__file__).resolve().parents[1])

    def tearDown(self):
        self.temp.cleanup()

    def test_config_and_state_are_pinned_to_same_commit(self):
        paths=[]
        def get(method,path):
            paths.append(path)
            if path=='git/ref/heads/main':return {'object':{'sha':'a'*40}}
            from _ftr_runtime import dictionary_rules as rules
            value=self.config if '_ftr_config' in path else rules.EMPTY if rules.FILE in path else {'version':1,'pending':{},'history':[]} if '_ftr_extraordinarias' in path else {'drive':{'read_utc':'REAL_SAVED_TIME'}}
            return {'content':base64.b64encode(json.dumps(value).encode()).decode()}
        with patch.object(server,'DATA',self.root),patch.object(server,'api',side_effect=get):
            value=main0631.snapshot()
        self.assertTrue(all(path.endswith('?ref='+'a'*40) for path in paths[1:]))
        self.assertEqual(value['state']['drive']['read_utc'],'REAL_SAVED_TIME')
        self.assertEqual(value['digest'],digest(self.config))

    def test_pending_query_recovers_request_beyond_panel_six(self):
        identifier='d'*32
        rows=[dict(id=n,status='completed',conclusion='success',display_title='Other',created_at='2026-10-21T19:00:00Z',path='.github/workflows/ftr_sincronizar.yml') for n in range(9)]
        rows.append(dict(id=99,status='completed',conclusion='success',display_title='FTR · drive · '+identifier,created_at='2026-10-21T18:00:00Z',path='.github/workflows/ftr_sincronizar.yml'))
        def get(method,path):
            if '/jobs?' in path:return {'total_count':1,'jobs':[{'steps':[{'name':'Procesar, validar, guardar y publicar','conclusion':'success'}]}]}
            if 'status=' in path:return {'total_count':0,'workflow_runs':[]}
            return {'total_count':len(rows),'workflow_runs':rows}
        with patch.object(server,'api',side_effect=get):
            result=main0631.pending_runs('2026-10-21T17:00:00+00:00')
        self.assertEqual(next(r for r in result if r['request_id']==identifier)['effect'],'updated')

    @unittest.skipUnless(os.name=='nt','La migración usa DPAPI de Windows')
    def test_existing_private_key_is_reused_without_rotation_or_deletion(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_ftr_admin'))
        from diagnostico_administrativo import seal
        key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        file=self.root/'LLAVE_PRIVADA_DIAGNOSTICO.pem'
        file.write_bytes(private)
        protected=seal({'incidencias':[]},public)
        with patch.object(server,'DATA',self.root),patch.object(server,'BUNDLE',self.root/'NO_BUNDLE'):
            self.assertEqual(server.unseal(protected),{'incidencias':[]})
            self.assertTrue((self.root/'diagnostico.dpapi').exists())
            self.assertNotIn(b'PRIVATE KEY',(self.root/'diagnostico.dpapi').read_bytes())
            self.assertEqual(server.unseal(protected),{'incidencias':[]})
        self.assertEqual(file.read_bytes(),private)


if __name__=='__main__':unittest.main()
