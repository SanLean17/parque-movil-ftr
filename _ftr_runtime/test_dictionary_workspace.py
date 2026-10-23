import copy
import json
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from _ftr_runtime import anomalies,dictionary_rules as rules,record_interpretation as records,mechanical_review as review
from _ftr_runtime import test_statistics_admin as fixtures

class InterpretationTests(unittest.TestCase):
    def contextual(self,component='tensores',**changes):
        return dict(expresion='punta',categoria=anomalies.OWNER[component],componente=component,tipo='descriptor',significado='extremo',habilitada=True,**changes)
    def test_contextual_descriptor_never_adds_another_component(self):
        d=rules.proposed(rules.EMPTY,[self.contextual()],rules.digest(rules.EMPTY));compiled=rules.compile_rules(d)
        for text in ('TENSOR PUNTA','PUNTA TENSOR'):
            value=anomalies.analyze(text,compiled)
            self.assertEqual(len(value['hallazgos']),1);self.assertEqual(value['pendientes'],[])
        for text in ('PUNTA','PF3 PUNTA','TENSOR POSIBLE PUNTA','TENSOR DESCONOCIDO PUNTA'):
            self.assertTrue(anomalies.analyze(text,compiled)['pendientes'])
        d=rules.proposed(d,d['reglas']+[self.contextual('pulmon_freno')],rules.digest(d))
        self.assertFalse(anomalies.analyze('PF3 PUNTA',rules.compile_rules(d))['pendientes'])
        d['reglas'][0]['habilitada']=False
        # Mismo archivo global, no diccionario por año.
        self.assertEqual(rules.validate(json.loads(rules.encoded(d))),d)
    def test_confirmed_code_punctuation_and_only_r4_position(self):
        for text in ('PF3','PF.3','PF 3','PF-3','P.F.3'):
            self.assertEqual(anomalies.analyze(text)['hallazgos'][0]['referencia'],'pf3')
        for text in ('PF-30','PF-3.5','PF\n3','PF palabra 3'):
            self.assertFalse(any(x['referencia']=='pf3' for x in anomalies.analyze(text)['hallazgos']))
        self.assertEqual(anomalies.analyze('R4')['hallazgos'][0]['ubicacion'],'trasero derecho interno')
        self.assertEqual(anomalies.analyze('R3')['hallazgos'][0]['ubicacion'],'trasero r3')
    def test_fragments_original_offsets_split_join_gaps_dedup_and_scope(self):
        text='BARRA CORTA TRAS, PF3, TENSOR SUPERIOR DERECHO, A2 SUELTO'
        parts=records.suggestions(text,rules.EMPTY);self.assertEqual(len(parts),4)
        self.assertEqual([text[f['inicio']:f['fin']] for f in parts],['BARRA CORTA TRAS','PF3','TENSOR SUPERIOR DERECHO','A2 SUELTO'])
        self.assertEqual(len(records.interpret(text,parts,rules.EMPTY)['hallazgos']),4)
        joined=[dict(inicio=0,fin=len(text),modo='automatico',hallazgos=[])]
        self.assertEqual(records.interpret(text,joined,rules.EMPTY),records.interpret(text,parts,rules.EMPTY))
        self.assertIn('PF3',records.interpret(text,[parts[0],*parts[2:]],rules.EMPTY)['pendientes'])
        repeated='PF3, PF3';self.assertEqual(len(records.interpret(repeated,records.suggestions(repeated,rules.EMPTY),rules.EMPTY)['hallazgos']),1)
        decomposed='  PULMO\u0301N DE FRENO, PF-3. A2 SUELTO  '
        self.assertEqual([decomposed[f['inicio']:f['fin']] for f in records.suggestions(decomposed,rules.EMPTY)],['PULMO\u0301N DE FRENO','PF-3','A2 SUELTO'])
        for bad in ([parts[0],parts[0]],[dict(parts[0],fin=len(text)+1)],[None],[dict(parts[0],inicio=True)]):
            with self.assertRaises(ValueError):records.validated(text,bad)
        event=dict(fecha='2026-01-02',linea=17,pestana='Linea 17',fila=2,dominio='AA111AA',estado='OBSERVADO',novedades='X12',tiene_novedades=True)
        rule=dict(expresion='X12',categoria='direccion',componente='barra_larga',habilitada=True)
        saved=records.correction(event,records.suggestions('X12',rules.EMPTY),rule)
        corrections={saved['registro_id']:saved}
        self.assertEqual(len(records.apply(event,corrections,rules.EMPTY)['hallazgos']),1)
        for changed in (dict(event,fila=3),dict(event,estado='SIN NOVEDAD'),dict(event,novedades='X12 '),dict(event,fecha='2027-01-02')):
            self.assertEqual(records.apply(changed,corrections,rules.EMPTY)['pendientes'],['X12'])
    def test_private_text_cannot_become_general_rule(self):
        for text in ('Juan','ANA','Luis','Pedro','AA111AA','dominio','persona@example.com','PF3 fila 2','<script>'):
            with self.assertRaises(ValueError):rules.expression(text)

class RolloverTests(unittest.TestCase):
    setUp=fixtures.HistoricalTests.setUp
    tearDown=fixtures.HistoricalTests.tearDown
    google=fixtures.HistoricalTests.google
    sheets=fixtures.HistoricalTests.sheets
    sheet=fixtures.HistoricalTests.sheet
    build=fixtures.HistoricalTests.build
    historical=fixtures.HistoricalTests.historical
    # Reutiliza el mismo lector con fuentes falsas; no una proyección inventada.
    def test_complete_rollover_preserves_two_archives_dictionary_and_cnrt(self):
        self.google(self.sheets());data,_,_=self.build(self.historical())
        from _ftr_runtime import historical_statistics as history
        history.add_archive(self.root,data)
        dictionary=rules.proposed(rules.EMPTY,[dict(expresion='X12',categoria='direccion',componente='barra_larga',habilitada=True)],rules.digest(rules.EMPTY))
        (self.root/rules.FILE).write_bytes(rules.encoded(dictionary))
        paths=['estadisticas/2025.json','estadisticas/2026.json',rules.FILE,'parques/linea36.csv','parques/linea37.csv']
        before={p:(self.root/p).read_bytes() for p in paths}
        self.config['period']=2027;self.config['sheetUrl']='https://docs.google.com/spreadsheets/d/NEXT_YEAR_FICTITIOUS_1234567/edit'
        self.clock=datetime(2027,2,3,20,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):self.google(self.sheets())
        self.assertFalse((self.root/'estadisticas/2027.json').exists())
        good=[self.sheet('LINEA 36/37',[['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],['01/02/2027',36,'AA111AA',1,'OBSERVADO','X12']])]
        # ROOT del motor es el repositorio global; root es el staging anual.
        loader=rules.load
        with patch.object(rules,'load',side_effect=lambda _:loader(self.root)):
            self.google(good)
        active=json.loads((self.root/'estadisticas/2027.json').read_bytes())
        self.assertEqual(active['totales']['registros_validos'],1)
        self.assertEqual(active['interpretacion']['sha256'],rules.digest(dictionary))
        self.assertEqual(active['anomalias']['identificadas'],1)
        for p,value in before.items():self.assertEqual((self.root/p).read_bytes(),value,p)
