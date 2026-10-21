import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from _ftr_runtime import worker


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = b'linea,fecha,dominio,interno\n36,01/10/2026,AA111AA,1\n'
        self.manifest = dict(version='fixture', files_sha256={'controlados/linea36.csv': hashlib.sha256(self.data).hexdigest()})
        (self.root/'ftr_publicacion.json').write_text(json.dumps(self.manifest))

    def tearDown(self):
        self.temp.cleanup()

    def response(self, url, **kwargs):
        self.assertEqual(kwargs['params']['ftr_revision'], 'fixture-revision')
        self.assertNotIn('Authorization', kwargs['headers'])
        return Mock(content=self.data, json=Mock(return_value=self.manifest))

    def test_web_manifest_and_bytes_confirm_publication(self):
        with patch.object(worker, 'ROOT', self.root), patch.object(requests, 'get', side_effect=self.response) as get:
            worker.verify_publication('fixture-revision')
        self.assertEqual(get.call_count, 2)

    def test_pages_green_but_stale_csv_is_not_published(self):
        with patch.object(worker, 'ROOT', self.root), patch.object(worker.time, 'sleep'), patch.object(requests, 'get', return_value=Mock(content=b'OLD', json=Mock(return_value=self.manifest))):
            with self.assertRaisesRegex(ValueError, 'Publicación pendiente'):
                worker.verify_publication('fixture-revision')

    def test_http_failure_does_not_erase_saved_files(self):
        before = (self.root/'ftr_publicacion.json').read_bytes()
        with patch.object(worker, 'ROOT', self.root), patch.object(worker.time, 'sleep'), patch.object(requests, 'get', side_effect=requests.ConnectionError):
            with self.assertRaises(ValueError):
                worker.verify_publication('fixture-revision')
        self.assertEqual(before, (self.root/'ftr_publicacion.json').read_bytes())

    def test_pages_result_requires_exact_commit(self):
        with patch.object(worker, 'gh', return_value={'commit':'other', 'status':'built'}), patch.object(worker.time, 'sleep'), patch.object(worker, 'verify_publication') as verify:
            with self.assertRaises(ValueError):
                worker.build_pages('fixture-revision')
            verify.assert_not_called()

    def test_built_pages_also_checks_web(self):
        with patch.object(worker, 'gh', return_value={'commit':'fixture-revision', 'status':'built'}), patch.object(worker.time, 'sleep'), patch.object(worker, 'verify_publication') as verify:
            worker.build_pages('fixture-revision')
            verify.assert_called_once_with('fixture-revision')
