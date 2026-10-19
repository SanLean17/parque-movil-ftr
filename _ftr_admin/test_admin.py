import base64
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnostico_administrativo as admin
base = admin.base
NOW = '2026-10-19T22:00:00+00:00'

def sheet(rows, title='LINEA 2', with_line=False):
    heads = ['FECHA', 'LÍNEA', 'DOMINIO', 'INTERNO', 'ESTADO'] if with_line else ['FECHA', 'DOMINIO', 'INTERNO', 'ESTADO']
    cells = {(1, 1): title}
    cells.update({(2, c): h for c, h in enumerate(heads, 1)})
    for r, values in enumerate(rows, 3):
        cells.update({(r, c): v for c, v in enumerate(values, 1) if v != ''})
    return base.Sheet(title, cells)

class AdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'parques').mkdir()
        (self.root/'controlados').mkdir()
    def tearDown(self):
        self.temp.cleanup()
    def fleet(self, line=2, data='AB123CD,2,1\n'):
        (self.root/'parques'/f'linea{line}.csv').write_text('dominio,linea,interno\n'+data, encoding='utf-8')
    def run_report(self, sh, configured=None):
        cfg = configured or {2:2058}
        report, records = base.analyze(sh, cfg, 2026, date(2026,10,19))
        base.add_comparison(report, records, self.root)
        private = admin.extend_report(report, sh, self.root, cfg, 'a'*30, NOW, date(2026,10,19))
        return report, private
    def test_enie_never_repaired(self):
        self.fleet(data='AB123CL,2,1\n')
        r,p=self.run_report([sheet([['01/01/2026','AB123CÑ',1,'SIN NOVEDAD']])])
        self.assertEqual(r['totales_estadisticas']['registros_validos'],0)
        i=p['incidencias'][0]
        self.assertEqual(i['dominio_ingresado'],'AB123CÑ')
        self.assertEqual(i['candidatos_mismo_interno'],[{'dominio':'AB123CL','interno':'1'}])
        self.assertEqual(i['celda'],'B3')
    def test_suggestions_same_line_only(self):
        self.fleet(9,'AB123CL,9,1\n')
        _,p=self.run_report([sheet([['01/01/2026','AB123CÑ',1,'']])])
        self.assertEqual(p['incidencias'][0]['candidatos_mismo_interno'],[])
    def test_ambiguous_internal_retains_all(self):
        self.fleet(data='AB123CL,2,1\nAC321LL,2,1\n')
        _,p=self.run_report([sheet([['01/01/2026','AB123CÑ',1,'']])])
        self.assertEqual(len(p['incidencias'][0]['candidatos_mismo_interno']),2)
    def test_historical_not_error(self):
        self.fleet()
        r,p=self.run_report([sheet([['01/01/2026','AC321LL',1,'']])])
        self.assertEqual(p['incidencias'][0]['codigo'],'NO_EN_PARQUE')
        self.assertEqual(p['incidencias'][0]['categoria'],'informacion')
        self.assertTrue(r['listo_para_revision_de_integracion'])
    def test_75_not_automatically_enabled(self):
        s=sheet([['01/01/2026',75,'AC321LL',1,'']], 'LINEA 2/75', True)
        r,p=self.run_report([s])
        self.assertEqual(p['incidencias'][0]['codigo'],'LINEA_NO_HABILITADA')
        self.assertEqual(r['totales_estadisticas']['registros_validos'],0)
        self.assertEqual(r['totales_estadisticas']['registros_lineas_no_habilitadas'],1)
    def test_one_vehicle_eight_visits(self):
        self.fleet()
        rows=[['01/01/2026','AB123CD',1,'SIN NOVEDAD'] for _ in range(8)]
        r,p=self.run_report([sheet(rows)])
        self.assertEqual(r['totales_estadisticas']['repeticiones_adicionales'],7)
        self.assertEqual(r['totales_estadisticas']['unidades_repetidas'],1)
        self.assertEqual(len(p['repetidos']),1)
    def test_two_vehicles_repeated(self):
        self.fleet()
        rows=[['01/01/2026',d,1,''] for d in ['AB123CD','AC321LL'] for _ in range(2)]
        r,p=self.run_report([sheet(rows)])
        self.assertEqual(r['totales_estadisticas']['repeticiones_adicionales'],2)
        self.assertEqual(r['totales_estadisticas']['unidades_repetidas'],2)
    def test_exact_duplicate_separate(self):
        rows=[['01/01/2026','AB123CD',1,''],['02/01/2026','AB123CD',1,''],['02/01/2026','AB123CD',1,'']]
        r,p=self.run_report([sheet(rows)])
        self.assertEqual(r['totales_estadisticas']['duplicados_exactos_adicionales'],1)
        self.assertEqual(r['totales_estadisticas']['repeticiones_adicionales'],2)
    def test_status_is_not_a_parser_error(self):
        self.fleet()
        r,p=self.run_report([sheet([['01/01/2026','AB123CD',1,'FUERA DE SERVICIO']])])
        self.assertEqual(r['totales_estadisticas']['registros_fuera_de_servicio'],1)
        self.assertEqual(r['incidencias_resumen']['por_categoria'].get('error',0),0)
    def test_status_not_inferred_from_unknown_label(self):
        r,_=self.run_report([sheet([['01/01/2026','AB123CD',1,'OTRO ESTADO']])])
        self.assertEqual(r['totales_estadisticas']['registros_fuera_de_servicio'],0)
        self.assertEqual(r['estadisticas'][0]['estado_no_clasificado'],1)
    def test_public_report_has_no_plates(self):
        self.fleet(data='AB123CL,2,99887\n')
        r,p=self.run_report([sheet([['01/01/2026','AB123CÑ',99887,'']])])
        data=json.dumps(r,ensure_ascii=False)
        for forbidden in ('AB123CÑ','AB123CL','99887'):
            self.assertNotIn(forbidden,data)
        self.assertIn('AB123CÑ',json.dumps(p,ensure_ascii=False))
    def test_only_email_from_secret(self):
        credential={'client_email':'bot@proyecto.iam.gserviceaccount.com','private_key':'NEVER_EXPORT_ME'}
        with patch.dict(os.environ,{'GOOGLE_SERVICE_ACCOUNT_JSON':json.dumps(credential)}):
            r,_=self.run_report([sheet([])])
        self.assertEqual(r['correo_bot_lector'],credential['client_email'])
        self.assertNotIn('NEVER_EXPORT_ME',json.dumps(r))
    def test_other_year_not_counted(self):
        r,p=self.run_report([sheet([['01/01/2025','AB123CD',1,'']])])
        self.assertEqual(r['totales_estadisticas']['registros_validos'],0)
        self.assertEqual(p['incidencias'][0]['codigo'],'OTRO_PERIODO')
    def test_date_error_is_visible(self):
        r,p=self.run_report([sheet([['31/02/2026','AB123CD',1,'']])])
        self.assertEqual(p['incidencias'][0]['codigo'],'FECHA_INVALIDA')
    def test_whitespace_does_not_invent_plate(self):
        self.fleet()
        r,p=self.run_report([sheet([['01/01/2026',' ab 123-cd ','001','']])])
        self.assertEqual(r['totales_estadisticas']['registros_validos'],1)
        self.assertEqual(p['incidencias'],[])
    def test_missing_fleet_not_zero(self):
        r,p=self.run_report([sheet([['01/01/2026','AB123CD',1,'']])])
        self.assertIsNone(r['estadisticas'][0]['pendientes_actuales'])
        self.assertEqual(p['incidencias'],[])
    def test_zero_fleet_coverage_undefined(self):
        self.fleet(data='')
        r,_=self.run_report([sheet([])])
        self.assertIsNone(r['estadisticas'][0]['cobertura_actual_pct'])
    def test_missing_internal_retains_domain_control(self):
        r,p=self.run_report([sheet([['01/01/2026','AB123CD','','']])])
        self.assertEqual(r['totales_estadisticas']['registros_validos'],1)
        self.assertEqual(p['incidencias'][0]['categoria'],'advertencia')
    def test_merged_date_is_not_lost(self):
        s=sheet([['01/01/2026','AB123CD',1,''],['','AC321LL',2,'']]);s.merges=[(3,1,4,1)]
        r,_=self.run_report([s]);self.assertEqual(r['totales_estadisticas']['registros_validos'],2)
    def test_empty_lines_and_blanks_continue(self):
        s=sheet([['01/01/2026','AB123CD',1,''],['','','',''],['','','',''],['','','',''],['02/01/2026','AC321LL',2,'']])
        r,_=self.run_report([s]);self.assertEqual(r['totales_estadisticas']['registros_validos'],2)
    def test_ciphertext_integrity(self):
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import padding,rsa
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
        private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        public=private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        sealed=admin.seal({'dominio':'AB123CÑ'},public)
        self.assertNotIn('AB123C',json.dumps(sealed))
        raw=private.decrypt(base64.b64decode(sealed['wrapped_key']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        clear=AESGCM(raw).decrypt(base64.b64decode(sealed['nonce']),base64.b64decode(sealed['ciphertext']),b'FTR-DIAGNOSTICO-3')
        self.assertEqual(json.loads(clear)['dominio'],'AB123CÑ')
        with self.assertRaises(InvalidTag):
            AESGCM(raw).decrypt(base64.b64decode(sealed['nonce']),base64.b64decode(sealed['ciphertext'])+b'x',b'FTR-DIAGNOSTICO-3')

if __name__=='__main__':unittest.main()
