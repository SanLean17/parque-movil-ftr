import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).parent))
import server

ROOT=Path(__file__).parent


class PanelResourcesTests(unittest.TestCase):
    def test_original_styles_and_empty_embedded_reports(self):
        html=(ROOT/'panel.html').read_text(encoding='utf-8')
        origin=json.loads((ROOT/'ORIGEN_063.json').read_text())
        styles='\n'.join(re.findall(r'<style>(.*?)</style>',html,re.S))
        self.assertEqual(hashlib.sha256(styles.encode()).hexdigest(),origin['styles_sha256'])
        self.assertIsNone(json.loads(re.search(r'id="ftrPrivateReport">(.*?)</script>',html,re.S)[1]))
        report=json.loads(re.search(r'id="ftrActualReport" type="application/json">(.*?)</script>',html,re.S)[1])
        self.assertEqual(report['estado'],'SIN_INFORME');self.assertEqual(report['lineas'],[])
        self.assertNotRegex(html,r'-----BEGIN (?:RSA )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{20}')
        self.assertNotIn('39342172033',html)
        self.assertEqual(re.findall(r'<script src="([^"]+)"',html),['/ftr-historial.js','/panel-history.js','/panel-bridge.js','/panel-statistics-admin.js'])

    def test_incomplete_new_package_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'panel.html').write_text('__FTR_CSRF__')
            with patch.object(server,'RESOURCE',root),patch.object(server,'VERSION','06.3.1'):
                with self.assertRaisesRegex(ValueError,'panel-bridge.js'):server.check_resources()

    def test_current_release_requires_every_runtime_resource(self):
        from _ftr_app.version import VERSION
        names=('panel-bridge.js','panel-statistics-admin.js','panel-history.js','ftr-historial.js')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'panel.html').write_text('__FTR_CSRF__')
            for name in names:(root/name).write_text('// recurso ficticio')
            with patch.object(server,'RESOURCE',root),patch.object(server,'VERSION',VERSION),patch.object(sys,'frozen',True,create=True):
                server.check_resources()
                for name in names:
                    with self.subTest(name=name):
                        (root/name).unlink()
                        with self.assertRaises(ValueError):server.check_resources()
                        (root/name).write_text('// recurso ficticio')


if __name__=='__main__':unittest.main()
