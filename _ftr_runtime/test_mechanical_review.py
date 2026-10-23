"""La vista previa no inventa deltas y el histórico no altera controles."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from _ftr_runtime import dictionary_rules as rules, mechanical_review as review, anomalies
from _ftr_runtime import historical_statistics as history, statistics_archive as archive
from _ftr_runtime.test_source_pipeline import SourcePipelineTests
from _ftr_tools.statistics_admin import apply
from _ftr_runtime.config import digest
from _ftr_runtime.public_statistics import STATUS

class ReviewTests(unittest.TestCase):
    setUp=SourcePipelineTests.setUp
    tearDown=SourcePipelineTests.tearDown
    sheet=SourcePipelineTests.sheet
    sheets=SourcePipelineTests.sheets
    google=SourcePipelineTests.google

    def source(self):
        return [self.sheet('Línea 999',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
            ['01/02/2025','AA111AA',7,'FUERA DE SERVICIO','JGO B LARGA; barra larga; JGO B LARGA'],
            ['02/02/2025','AA111AA',7,'OBSERVADO','JGO B LARGA'],
            ['03/02/2025','BB222BB',8,'SIN NOVEDAD','posible JGO B LARGA'],
            ['04/02/2025','CC333CC',9,'','JGO B LARGA suspensión']])]

    def build(self,dictionary=None):
        return history.build(self.source(),2025,'HISTORICAL_SOURCE_1234567','2026-10-22T22:00:00+00:00',dictionary or rules.EMPTY)

    def candidate(self):
        return rules.proposed(rules.EMPTY,[dict(expresion='JGO B LARGA',categoria='direccion',componente='barra_larga',habilitada=True)],rules.digest(rules.EMPTY))

    def test_exact_preview_groups_originals_states_and_deduplicates(self):
        data,report,detail=self.build()
        private=detail['novedades_sin_clasificar'];snap=private['revision_mecanica']
        originals=copy.deepcopy(snap);effect=review.preview(snap,self.candidate())
        self.assertEqual(snap,originals)
        grouped=next(r for r in private['pendientes'] if r['expresion']=='JGO B LARGA')
        self.assertEqual(grouped['frecuencia'],2)
        self.assertEqual(grouped['estados']['fuera_de_servicio'],1)
        self.assertEqual(grouped['estados']['observado'],1)
        self.assertEqual(grouped['referencias'][0]['estado_formal'],'FUERA DE SERVICIO')
        self.assertEqual(grouped['referencias'][0]['dominio'],'AA111AA')
        self.assertEqual(len(grouped['referencias'][0]['registro_id']),64)
        self.assertEqual(effect['antes']['sin_clasificar']-effect['despues']['sin_clasificar'],2)
        # El primer registro ya tenía barra larga: deduplicación real.
        self.assertEqual(effect['despues']['identificadas']-effect['antes']['identificadas'],1)
        self.assertEqual(effect['registros'],4)
        self.assertEqual(effect['antes']['cobertura'],effect['despues']['cobertura'])
        for term in ('AA111AA','JGO B LARGA','novedades_original'):self.assertNotIn(term,json.dumps(data))

    def test_tensors_suspension_and_specific_direction(self):
        for text in ('tensor delantero','tensores traseros flojos','tensor de posicionamiento del eje'):
            self.assertIn('tensores',[r['componente'] for r in anomalies.analyze(text)['hallazgos']])
        self.assertEqual(anomalies.analyze('tensor de dirección')['hallazgos'],[])
        specific=anomalies.analyze('tensor de barra larga con juego')
        self.assertEqual([r['componente'] for r in specific['hallazgos']],['barra_larga'])
        self.assertEqual(anomalies.analyze('sin juego en tensor delantero')['hallazgos'],[])

    def test_literal_conflicts_privacy_and_context(self):
        candidate=self.candidate();compiled=rules.compile_rules(candidate)
        for text in ('posible JGO B LARGA','sin juego de JGO B LARGA','JGO B LARGA suspensión','JGO B LARGA dirección suspensión'):
            self.assertNotIn('barra_larga',[r['componente'] for r in anomalies.analyze(text,compiled)['hallazgos']])
        for expression in ('juego','jgo','AA111AA','JGO B LARGA AA111AA','JGO.*','JGO B LARGA\nsecreto','no funciona','roto flojo','jgo de la'):
            with self.subTest(expression=expression),self.assertRaises(ValueError):
                rules.validate(dict(version=1,revision=1,reglas=[dict(candidate['reglas'][0],expresion=expression)]))
        with self.assertRaises(ValueError):rules.proposed(candidate,candidate['reglas']+[dict(candidate['reglas'][0],expresion='b larga')],rules.digest(candidate))

    def test_report_corruption_or_missing_snapshot_blocks_preview(self):
        data,report,detail=self.build();snap=detail['novedades_sin_clasificar']['revision_mecanica']
        with self.assertRaises(ValueError):review.preview(None,self.candidate())
        bad=copy.deepcopy(snap);bad['registros'][0]['estado']='sin novedad'
        with self.assertRaises(ValueError):review.preview(bad,self.candidate())
        bad=copy.deepcopy(snap);bad['estadisticas']['totales']['unidades_unicas_por_linea']+=1
        with self.assertRaises(ValueError):review.preview(bad,self.candidate())

    def test_historical_review_then_recalculation_isolated_and_preserves_original(self):
        self.google(self.sheets())
        from _ftr_runtime.worker import public_hashes
        (self.root/'_ftr_config.json').write_text(json.dumps(self.config))
        (self.root/'_ftr_admin').mkdir(exist_ok=True)
        (self.root/'_ftr_admin/diagnostico_publica.pem').write_bytes(b'fake')
        (self.root/'ftr_publicacion.json').write_text(json.dumps({'files_sha256':public_hashes(self.root,self.config)}))
        old,_,_=self.build();archive.publish(self.root,json.loads((self.root/'estadisticas_ftr.json').read_bytes()))
        history.add_archive(self.root,old)
        self.root.joinpath('_ftr_diccionario.json').write_bytes(rules.encoded(self.candidate()))
        old_bytes=(self.root/'estadisticas/2025.json').read_bytes()
        active=(self.root/'estadisticas_ftr.json').read_bytes()
        # El sello se prepara desde los datos ficticios; no necesita una llave real.
        payload=dict(period=2025,sheetUrl='https://docs.google.com/spreadsheets/d/HISTORICAL_SOURCE_1234567/edit',
                     allow_partial=False,expected_archive=hashlib.sha256(old_bytes).hexdigest(),expected_dictionary=rules.digest(self.candidate()))
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as temp:
            with patch('test_mechanical_review.history.admin.base.decode_xlsx',return_value=self.source()),patch('test_mechanical_review.history.admin.seal',return_value={'encrypted':True}) as sealed:
                reportdir=Path(temp)/'report'
                paths=apply(self.root,'history-review',payload,digest(self.config),export=lambda _:b'fake',report_dir=reportdir)
                self.assertEqual(paths,[])
                for name,value in before.items():self.assertEqual((self.root/name).read_bytes(),value)
                fresh,_,detail=self.build(self.candidate());capsule=detail['novedades_sin_clasificar']['revision_mecanica']
                payload.update(expected_records=capsule['huella_registros'],expected_result=review.fingerprint(fresh['anomalias']))
                with self.assertRaises(ValueError):apply(self.root,'history-recalculate',dict(payload,expected_result='0'*64),digest(self.config),export=lambda _:b'fake')
                paths=apply(self.root,'history-recalculate',payload,digest(self.config),export=lambda _:b'fake',report_dir=reportdir)
                completed=sealed.call_args.args[0]['novedades_sin_clasificar']['revision_mecanica']
                self.assertEqual(completed['sha256_archivo'],hashlib.sha256((self.root/'estadisticas/2025.json').read_bytes()).hexdigest())
                self.assertEqual(completed['sha256_anterior'],payload['expected_archive'])
                review.unpack(completed)
        self.assertEqual((self.root/'estadisticas_ftr.json').read_bytes(),active)
        revised=json.loads((self.root/'estadisticas/2025.json').read_bytes())
        review.unchanged_controls(old,revised)
        self.assertEqual(revised['lectura_planilla_utc'],old['lectura_planilla_utc'])
        self.assertEqual((self.root/f"estadisticas/revisiones/2025/{payload['expected_archive']}.json").read_bytes(),old_bytes)
        self.assertFalse(any(p.startswith(('controlados/','parques/','historial/')) for p in paths))
        for name,value in before.items():
            if name not in paths:self.assertEqual((self.root/name).read_bytes(),value,name)
        archive.validate_collection(self.root)
        for name in paths:
            for private in ('AA111AA','JGO B LARGA','novedades_original'):self.assertNotIn(private,(self.root/name).read_text())
