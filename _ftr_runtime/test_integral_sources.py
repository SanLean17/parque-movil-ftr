"""Defectos de identidad y estructura reproducidos con fuentes ficticias."""
import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from _ftr_pruebas import planilla_anual as base
from _ftr_runtime import worker
from _ftr_runtime.config import load, digest


def sheet(name, rows):
    return base.Sheet(name, {(r,c):v for r,row in enumerate(rows,1) for c,v in enumerate(row,1) if v})


class IntegrityTests(unittest.TestCase):
    def test_non_ascii_domain_must_not_become_valid_by_uppercase(self):
        for value in ('Aß123', 'AA123ſſ', 'AA１２３AA', 'AA١٢٣AA', 'AÑ123AA'):
            with self.subTest(value=value):
                self.assertEqual(base.plate(value), '')
        self.assertEqual(base.plate('an123na'), 'AN123NA')

    def test_control_table_without_line_identity_is_reported(self):
        tables = [sheet('LINEA 36', [['FECHA','DOMINIO','INTERNO']]),
                  sheet('Nueva pestaña', [['FECHA','DOMINIO','INTERNO'],['01/10/2026','AA111AA',1]])]
        report, _ = base.analyze(tables, {36:9999}, 2026, date(2026,10,21))
        self.assertTrue(report['ubicaciones_a_revisar'])
        self.assertEqual(report['estado'], 'REVISAR')

    def test_unknown_incomplete_table_does_not_disappear(self):
        tables = [sheet('LINEA 36', [['FECHA','DOMINIO','INTERNO']]),
                  sheet('Nuevos controles', [['FECHA','DOMINIO'],['01/10/2026','AA111AA']])]
        report, _ = base.analyze(tables, {36:9999}, 2026, date(2026,10,21))
        self.assertTrue(report['ubicaciones_a_revisar'])

    def test_bad_domain_from_other_year_does_not_block_new_period(self):
        tables = [sheet('LINEA 36', [['FECHA','DOMINIO','INTERNO'],['01/01/2025','INVALIDO',1]])]
        report, records = base.analyze(tables, {36:9999}, 2026, date(2026,10,21))
        self.assertEqual(report['estado'], 'VACIA_VALIDA')
        self.assertFalse(records)

    def test_incident_preserves_enye_then_disappears_after_source_correction(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'_ftr_admin'))
        import diagnostico_administrativo as admin
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'parques').mkdir()
            (root/'parques/linea36.csv').write_text('dominio,interno,linea\nAN123NA,7,36\n')
            (root/'ultima_actualizacion_parque.txt').write_text('2026-10-20T01:00:00Z\n')
            table = sheet('LINEA 36', [['FECHA','DOMINIO','INTERNO'],['01/10/2026','AÑ123NA',7]])
            report, _ = admin.base.analyze([table], {36:9999}, 2026, date(2026,10,21))
            detail = admin.extend_report(report,[table],root,{36:9999},'FAKE_SHEET','2026-10-21T20:00:00Z',date(2026,10,21))
            row = next(x for x in detail['incidencias'] if x['codigo']=='DOMINIO_INVALIDO')
            self.assertEqual(row['dominio_ingresado'], 'AÑ123NA')
            self.assertEqual(row['candidatos_mismo_interno'], [dict(dominio='AN123NA',interno='7')])
            self.assertEqual(row['referencia_parque']['fecha_lectura_utc'], '2026-10-20T01:00:00Z')
            table.cells[2,2] = 'AN123NA'
            report, _ = admin.base.analyze([table], {36:9999}, 2026, date(2026,10,21))
            detail = admin.extend_report(report,[table],root,{36:9999},'FAKE_SHEET','2026-10-21T21:00:00Z',date(2026,10,21))
            self.assertFalse(any(x['codigo']=='DOMINIO_INVALIDO' for x in detail['incidencias']))


if __name__ == '__main__':
    unittest.main()
