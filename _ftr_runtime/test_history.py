import hashlib
import json
import unittest
from _ftr_runtime import test_source_pipeline as fixtures


class PublishedHistoryTests(unittest.TestCase):
    setUp = fixtures.SourcePipelineTests.setUp
    tearDown = fixtures.SourcePipelineTests.tearDown
    sheet = fixtures.SourcePipelineTests.sheet
    sheets = fixtures.SourcePipelineTests.sheets
    google = fixtures.SourcePipelineTests.google
    def test_history_is_built_from_all_valid_events_without_private_fields(self):
        self.google(self.sheets())
        data=json.loads((self.root/'historial/linea36.json').read_text(encoding='utf-8'))
        self.assertEqual(data['controles_sha256'],hashlib.sha256((self.root/'controlados/linea36.csv').read_bytes()).hexdigest())
        self.assertEqual(data['periodo'],2026)
        self.assertEqual(data['linea'],36)
        self.assertEqual([r['fecha'] for r in data['controles']],['2026-10-01','2026-10-20'])
        self.assertTrue(all(set(r)=={'dominio','fecha','interno'} for r in data['controles']))
        self.assertFalse((self.root/'historial/linea999.json').exists())
        self.assertEqual(data['lectura_planilla_utc'],self.clock.isoformat())

    def test_failed_read_preserves_existing_history_and_new_period_is_not_mixed(self):
        self.google(self.sheets());file=self.root/'historial/linea36.json';original=file.read_bytes()
        invalid=self.sheets();invalid[0].cells[3,3]='AB12CÑ'
        with self.assertRaises(ValueError):self.google(invalid)
        self.assertEqual(file.read_bytes(),original)
        self.config['period']=2027;self.google(self.sheets())
        data=json.loads(file.read_text(encoding='utf-8'));self.assertEqual(data['periodo'],2027);self.assertEqual(data['controles'],[])
