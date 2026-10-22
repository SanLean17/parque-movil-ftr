"""Lector, diagnóstico y CSV reales sobre fuentes ficticias; sin red."""
import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import actualizar_parques as parks
from _ftr_runtime import worker
from _ftr_runtime.config import load

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'_ftr_admin'))
import diagnostico_administrativo as admin


class SourcePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ('parques', 'controlados'):
            (self.root/folder).mkdir()
        self.config = load(worker.ROOT)
        self.config['lines'] = [dict(line=n, company=9999, enabled=True) for n in (36, 37)]
        self.config['period'] = 2026
        self.clock = datetime(2026, 10, 21, 20, 1, tzinfo=timezone.utc)
        for number, domain in [(36, 'AA111AA'), (37, 'BB222BB')]:
            (self.root/'parques'/f'linea{number}.csv').write_text(f'dominio,interno,linea,empresaNro\n{domain},1,{number},9999\n')
            (self.root/'controlados'/f'linea{number}.csv').write_text(f'linea,fecha,dominio,interno\n{number},01/01/2026,{domain},1\n')

    def tearDown(self):
        self.temp.cleanup()

    def sheet(self, name, rows):
        return admin.base.Sheet(name, {(r,c):v for r,row in enumerate(rows,1) for c,v in enumerate(row,1) if v})

    def sheets(self):
        return [self.sheet('LINEA 36/37', [
            ['FECHA','LINEA','DOMINIO','INTERNO','ESTADO'],
            ['01/10/2026',36,'AA111AA',1,'SIN NOVEDAD'],
            ['20/10/2026',36,'AA111AA',2,'FUERA DE SERVICIO'],
            ['03/10/2026',37,'BB222BB',1,'SIN NOVEDAD'],
            ['01/10/2025',37,'CC333CC',2,'SIN NOVEDAD'],
        ]), self.sheet('LINEA 999', [
            ['FECHA','DOMINIO','INTERNO'], ['01/10/2026','DD444DD',1]
        ])]

    def google(self, sheets):
        with ExitStack() as stack:
            stack.enter_context(patch.object(worker, 'REPORT_DIR', self.root/'reports'))
            stack.enter_context(patch.object(worker, 'now', return_value=self.clock))
            stack.enter_context(patch.object(admin.base, 'export_sheet', return_value=b'FAKE_XLSX'))
            stack.enter_context(patch.object(admin.base, 'decode_xlsx', return_value=sheets))
            return worker.google_snapshot(self.root, self.config)

    def test_multiple_tabs_lines_latest_date_and_repeated_controls(self):
        data = self.google(self.sheets())
        self.assertEqual((data['records'], data['unique']), (3, 2))
        with (self.root/'controlados/linea36.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows, [dict(linea='36', fecha='20/10/2026', dominio='AA111AA', interno='2')])
        self.assertFalse((self.root/'controlados/linea999.csv').exists())
        summary = (self.root/'reports/resumen.json').read_text(encoding='utf-8')
        self.assertNotIn('AA111AA', summary)
        self.assertTrue((self.root/'reports/detalle_admin.enc.json').exists())

    def test_missing_sheet_preserves_all_prior_controls(self):
        old = {p.name:p.read_bytes() for p in (self.root/'controlados').glob('*.csv')}
        with self.assertRaisesRegex(ValueError, 'se conservaron'):
            self.google([self.sheet('LINEA 36', [['FECHA','DOMINIO','INTERNO']])])
        self.assertEqual(old, {p.name:p.read_bytes() for p in (self.root/'controlados').glob('*.csv')})

    def test_auxiliary_tabs_do_not_block_publish_or_enter_stats_and_history(self):
        sheets = self.sheets()
        auxiliary = self.sheet('Resumen Linea 36', [
            ['FECHA','LINEA','DOMINIO','INTERNO','ESTADO'],
            ['21/10/2026',36,'EE555EE',9,'FUERA DE SERVICIO'],
            ['incorrecta',36,'incorrecta',9,''],
        ])
        unidentified = self.sheet('Auxiliar', [[], [], ['FECHA','DOMINIO','INTERNO'], ['21/10/2026','FF666FF',1]])
        sheets = [auxiliary, sheets[0], unidentified, sheets[1]]
        data = self.google(sheets)
        self.assertEqual((data['records'], data['unique']), (3, 2))
        report = json.loads((self.root/'reports/resumen.json').read_text(encoding='utf-8'))
        self.assertTrue(report['listo_para_revision_de_integracion'])
        self.assertEqual(report['totales_estadisticas']['registros_validos'], 3)
        self.assertEqual(report['totales_estadisticas']['registros_fuera_de_servicio'], 1)
        self.assertEqual(report['ubicaciones_a_revisar'], [])
        self.assertEqual({r['pestana_posicion'] for r in admin.source_rows(sheets)}, {2, 4})
        history = json.loads((self.root/'historial/linea36.json').read_text(encoding='utf-8'))
        self.assertEqual([r['dominio'] for r in history['controles']], ['AA111AA', 'AA111AA'])
        self.assertNotIn('EE555EE', (self.root/'controlados/linea36.csv').read_text())

    def test_valid_empty_table_and_period_change_do_not_mix_years(self):
        self.config['period'] = 2027
        data = self.google(self.sheets())
        self.assertEqual(data['records'], 0)
        self.assertEqual(len((self.root/'controlados/linea36.csv').read_text().splitlines()), 1)

    def test_invalid_domain_is_reported_without_guessing_or_publication(self):
        sheets = self.sheets()
        sheets[0].cells[3,3] = 'AA11IAA'
        before = (self.root/'controlados/linea36.csv').read_bytes()
        with self.assertRaises(ValueError):
            self.google(sheets)
        self.assertEqual(before, (self.root/'controlados/linea36.csv').read_bytes())
        report = json.loads((self.root/'reports/resumen.json').read_text(encoding='utf-8'))
        self.assertTrue(any(x['fila'] == 3 and x['celda'] == 'C3' for x in report['incidencias_resumen']['ubicaciones']))

    def test_shared_company_is_downloaded_once_and_two_fleets_validated(self):
        scripts = []
        def simulate_command(args, cwd, **kwargs):
            work = Path(cwd)
            scripts.append(Path(args[1]).name)
            if scripts[-1] == 'scraper.py':
                mapping = {}
                exec((work/'configuracion_lineas.py').read_text(), mapping)
                self.assertEqual(mapping['EMPRESAS_CNRT'], [9999])
                (work/'cnrt').mkdir()
                (work/'cnrt/empresa_9999.csv').write_text('dominio,interno,linea,empresaNro\nAA111AA,1,36,9999\nBB222BB,1,37,9999\nCC333CC,1,36OP1,9999\n')
            else:
                with patch.object(parks, 'CARPETA_CNRT', work/'cnrt'), patch.object(parks, 'CARPETA_PARQUES', work/'parques'), patch.object(parks, 'LINEAS_EMPRESAS', {36:9999,37:9999}):
                    parks.procesar()
            return subprocess.CompletedProcess(args, 0)
        with patch.object(worker.subprocess, 'run', side_effect=simulate_command):
            result = worker.cnrt_snapshot(self.root, self.config)
        self.assertEqual(scripts, ['scraper.py', 'actualizar_parques.py'])
        self.assertEqual((result['companies'],result['lines']), (1,2))
        self.assertNotIn('CC333CC', (self.root/'parques/linea36.csv').read_text())
