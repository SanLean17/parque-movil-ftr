"""Regresiones de auditoría. Solo fixtures ficticios y respuestas simuladas."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import actualizar_parques as parks
from _ftr_runtime.config import load, encoded, enabled
from _ftr_pruebas import planilla_anual as annual

ROOT = Path(__file__).resolve().parents[1]


class AuditRegressions(unittest.TestCase):
    def test_alphanumeric_cnrt_codes_are_not_lines(self):
        self.assertEqual(parks.extraer_lineas('195, 2077IE, 2077OE, 2077OP1'), {'195'})
        self.assertFalse(parks.pertenece_a_linea('195OP1', 195))
        self.assertEqual(parks.extraer_lineas('195.0; 36 / 37|38'), {'195', '36', '37', '38'})

    def test_shared_company_is_split_by_exact_line(self):
        frame = pd.DataFrame([
            {'dominio': 'AA111AA', 'linea': '36', 'empresaNro': '9999'},
            {'dominio': 'BB222BB', 'linea': '37', 'empresaNro': '9999'},
            {'dominio': 'CC333CC', 'linea': '36OP1', 'empresaNro': '9999'},
            {'dominio': 'DD444DD', 'linea': '36', 'empresaNro': '8888'},
        ])
        result = parks.filtrar_por_linea(frame, 36, 9999, 'fixture.csv')
        self.assertEqual(result['dominio'].tolist(), ['AA111AA'])

    def test_malformed_cnrt_row_rejects_entire_download(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'empresa_9999.csv'
            file.write_text('dominio,linea,empresaNro\nAA111AA,36,9999\nBB222BB,36,9999,EXTRA\n', encoding='utf-8')
            with self.assertRaises((RuntimeError, ValueError)):
                parks.leer_csv_cnrt(file)

    def test_diagnostics_follow_central_add_disable_and_remove(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'configuracion_lineas.py').write_text('LINEAS_EMPRESAS = {2: 2058}\n')
            cfg = load(ROOT)
            cfg['lines'] = [dict(line=36, company=9999, enabled=True), dict(line=37, company=9999, enabled=False)]
            (root / '_ftr_config.json').write_bytes(encoded(cfg))
            self.assertEqual(annual.configuration(root), {36: 9999})

    def test_invalid_central_config_never_falls_back_to_old_list(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'configuracion_lineas.py').write_text('LINEAS_EMPRESAS = {2: 2058}\n')
            (root / '_ftr_config.json').write_text('{}')
            with self.assertRaises(ValueError):
                annual.configuration(root)


if __name__ == '__main__':
    unittest.main()
