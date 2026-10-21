import copy
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import server
from _ftr_app.migration import import_archive
from _ftr_admin.diagnostico_administrativo import seal
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.pem=cls.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        cls.pub=cls.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.report=dict(modo='DIAGNOSTICO_SIN_PUBLICAR',periodo=2026,revision_repositorio='a'*40,
                         inicio_lectura_utc='2026-10-20T10:00:00+00:00',lineas=[])
        self.detail=dict(version=3,periodo=2026,revision_repositorio='a'*40,
                         detectado_utc=self.report['inicio_lectura_utc'],incidencias=[])

    def tearDown(self):self.temp.cleanup()

    def archive(self, report=None, detail=None):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('original/LLAVE_PRIVADA_DIAGNOSTICO.pem',self.pem)
            z.writestr('original/resumen.json',json.dumps(report or self.report))
            z.writestr('original/detalle_admin.enc.json',json.dumps(seal(detail or self.detail,self.pub)))
            z.writestr('../not-extracted.exe',b'NEVER EXECUTE OR EXTRACT')
        stream.seek(0);return stream

    def test_bad_or_mismatched_archive_writes_nothing(self):
        for source in [io.BytesIO(b'not a zip'),self.archive(detail={**self.detail,'periodo':2027})]:
            with self.assertRaises(ValueError):
                import_archive(source,self.root,server.protect,lambda:None,server.atomic_bytes)
            self.assertEqual(list(self.root.iterdir()),[])

    @unittest.skipUnless(os.name=='nt','DPAPI Windows')
    def test_private_zip_migrates_protected_and_keeps_latest_and_authorization(self):
        (self.root/'github.dpapi').write_bytes(b'PREEXISTING_AUTH_UNCHANGED')
        with patch.object(server,'DATA',self.root):
            value=import_archive(self.archive(),self.root,server.protect,server.diagnostic_cache,server.atomic_bytes)
            self.assertTrue(value['ok'])
            self.assertEqual(server.protect((self.root/'diagnostico.dpapi').read_bytes(),True),self.pem)
            self.assertEqual(server.diagnostic_cache()['details'],self.detail)
            self.assertNotIn(b'PRIVATE KEY',(self.root/'diagnostico.dpapi').read_bytes())
            first=(self.root/'informe.dpapi').read_bytes()
            older={**self.report,'inicio_lectura_utc':'2025-01-01T00:00:00+00:00'}
            import_archive(self.archive(older,{**self.detail,'detectado_utc':older['inicio_lectura_utc']}),self.root,server.protect,server.diagnostic_cache,server.atomic_bytes)
            self.assertEqual((self.root/'informe.dpapi').read_bytes(),first)
        self.assertEqual((self.root/'github.dpapi').read_bytes(),b'PREEXISTING_AUTH_UNCHANGED')
        self.assertEqual(set(p.name for p in self.root.iterdir()),{'github.dpapi','diagnostico.dpapi','informe.dpapi'})

    @unittest.skipUnless(os.name=='nt','DPAPI Windows')
    def test_another_private_key_is_not_replaced(self):
        different=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        raw=different.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        old=server.protect(raw);(self.root/'diagnostico.dpapi').write_bytes(old)
        with self.assertRaisesRegex(ValueError,'otra llave'):
            import_archive(self.archive(),self.root,server.protect,lambda:None,server.atomic_bytes)
        self.assertEqual((self.root/'diagnostico.dpapi').read_bytes(),old)
        self.assertFalse((self.root/'informe.dpapi').exists())

    def test_theme_persists_separately_and_requires_session(self):
        with patch.object(server,'DATA',self.root):
            client=server.app.test_client();base=server.ORIGIN
            headers={'Origin':base,'X-FTR-CSRF':server.CSRF}
            self.assertEqual(client.post('/api/preferences',base_url=base,json={'theme':'dark'},headers=headers).status_code,403)
            client.get('/iniciar/'+server.BOOT,base_url=base)
            self.assertEqual(client.post('/api/preferences',base_url=base,json={'theme':'dark'},headers=headers).status_code,200)
            self.assertEqual(json.loads((self.root/'preferencias.json').read_text()),{'theme':'dark'})
            self.assertFalse((self.root/'borrador.json').exists())
            self.assertEqual(client.post('/api/preferences',base_url=base,json={'theme':'bad'},headers=headers).status_code,400)


if __name__=='__main__':unittest.main()
