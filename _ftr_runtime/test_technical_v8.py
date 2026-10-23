"""FTR confirmed terminology, all fixtures synthetic and publication isolated."""
import copy
import json
import unittest
from datetime import date
from _ftr_runtime import anomalies as a, dictionary_rules as rules, public_statistics as stats
from _ftr_runtime import mechanical_review as review, historical_statistics as historical
from _ftr_runtime import test_mechanical_review as fixtures

def finding(component,reference=None,position='sin_ubicacion',defect='no_identificado',part=None,subpart=None,quantity=None):
    return (component,reference,position,defect,part,subpart,quantity)

CASES={
 'pulmón de freno 1, pinchado':[finding('pulmon_freno','pf1','delantero izquierdo','pinchadura')],
 'PF1 pinchado':[finding('pulmon_freno','pf1','delantero izquierdo','pinchadura')],
 'bloqueo':[finding('bloqueo_frenos')],
 'bloqueo no funciona':[finding('bloqueo_frenos',defect='no_funciona')],
 'amortiguador delantero derecho gira':[finding('amortiguadores',position='delantero derecho',defect='flojo')],
 'tensor sup e inf moño tras':[finding('tensores',position=p,part='moño trasero',quantity=1) for p in ('superior','inferior')],
 'tensor superior e inferior moño trasero':[finding('tensores',position=p,part='moño trasero',quantity=1) for p in ('superior','inferior')],
 'cardan cr 2, barra corta delantero':[finding('cruceta_direccion','cr2'),finding('barra_corta',position='delantero')],
 'cardan CR2':[finding('cruceta_direccion','cr2')],
 'cruceta 3 con juego':[finding('cruceta_direccion','cr3',defect='juego')],
 'barra corta ambos extremos con juego y cruceta 3 con juego':[finding('barra_corta',defect='juego',part='ambos extremos'),finding('cruceta_direccion','cr3',defect='juego')],
 'A 5y6 sueltos':[finding('amortiguadores','a5','trasero izquierdo','suelto',quantity=1),finding('amortiguadores','a6','trasero derecho','suelto',quantity=1)],
 'A5-A6 sueltos':[finding('amortiguadores','a5','trasero izquierdo','suelto',quantity=1),finding('amortiguadores','a6','trasero derecho','suelto',quantity=1)],
 'amortiguador 3,5y 4 y pf4':[finding('amortiguadores',r,p,quantity=1) for r,p in [('a3','trasero izquierdo'),('a5','trasero izquierdo'),('a4','trasero derecho')]]+[finding('pulmon_freno','pf4','trasero derecho')],
 'pulmón de freno 1 y 4':[finding('pulmon_freno','pf1','delantero izquierdo',quantity=1),finding('pulmon_freno','pf4','trasero derecho',quantity=1)],
 'amortiguador suelto 1':[finding('amortiguadores','a1','delantero izquierdo','suelto')],
 'señal sonora':[finding('sonora_marcha_atras')],
 'señal acústica marcha atrás no funciona':[finding('sonora_marcha_atras',defect='no_funciona')],
 'chicharra no funciona':[finding('sonora_marcha_atras',defect='no_funciona')],
 'corta pitman':[finding('barra_corta',part='lado pitman')],
 'barra corta lado eje':[finding('barra_corta',part='lado eje')],
 'pulmón de freno trasero izquierdo diafragma':[finding('pulmon_freno',position='trasero izquierdo',subpart='diafragma')],
 'flexible pulmón de freno delantero izquierdo, r3 lisa y amortiguador 3 suleto':[finding('flexibles_freno',position='delantero izquierdo'),finding('neumaticos_traseros','r3','trasero izquierdo interno','liso'),finding('amortiguadores','a3','trasero izquierdo','suelto')],
 'ambos neumáticos traseros internos cortados y barra corta lado Pitman con juego':[finding('neumaticos_traseros',position='trasero interno',defect='corte',quantity=2),finding('barra_corta',part='lado pitman',defect='juego')],
 'barra estabilizadora y amortiguador de dirección, chicharra':[finding(c) for c in ('barra_estabilizadora','amortiguador_direccion','sonora_marcha_atras')],
 'buge amortiguador 3':[finding('bujes','a3','trasero izquierdo')],
 'barra corta completa, larga derecha':[finding('barra_corta',part='ambos extremos'),finding('barra_larga',position='derecho')],
 'amortiguadores ambos delanteros con juego':[finding('amortiguadores',position='delantero',defect='juego',quantity=2)],
 'no coincide Kit':[],
 'expresión completamente desconocida':[],
}
DICTIONARY=rules.validate(dict(version=1,revision=4,reglas=[dict(expresion='extremo',variantes=['extremos'],tipo='descriptor',significado='extremo',alcance='general',habilitada=True)]))

class TechnicalV8Tests(unittest.TestCase):
    def test_all_thirty_cases_attributes_originals_formal_states_and_counts(self):
        self.assertEqual(len(CASES),30)
        for text,expected in CASES.items():
            for state in ('OBSERVADO','FUERA DE SERVICIO','SIN NOVEDAD'):
                with self.subTest(text=text,state=state):
                    e=dict(fecha=date(2026,2,1),linea=999,dominio='AA111AA',interno=1,estado=state,estado_original=state,tiene_novedades=True,novedades=text)
                    before=copy.deepcopy(e);result=a.analyze(text,rules.compile_rules(DICTIONARY))
                    fields=('componente','referencia','ubicacion','defecto','parte','subcomponente','cantidad_fisica')
                    self.assertCountEqual([tuple(f[k] for k in fields) for f in result['hallazgos']],expected)
                    self.assertEqual(result['pendientes'],[] if expected else [text])
                    total,private=stats.mechanics([e],dictionary=DICTIONARY)
                    self.assertEqual(e,before);self.assertEqual(total['cobertura']['registros_validos'],1)
                    self.assertEqual(total['identificadas'],len(expected))
                    self.assertEqual(total['elementos_fisicos']['cantidad_confirmada'],sum(f[-1] or 0 for f in expected))
                    actual_state={'OBSERVADO':'observado','FUERA DE SERVICIO':'fuera_de_servicio','SIN NOVEDAD':'sin_novedad'}[state]
                    self.assertEqual(sum(c['estados'][actual_state] for cat in total['categorias'] for c in cat['componentes']),len(expected)+(not expected))
                    for f in result['hallazgos']:self.assertIn(f['componente'],a.CATEGORIES[f['categoria']])
                    self.assertNotIn('AA111AA',json.dumps(total))

    def test_references_boundaries_ambiguity_and_specific_transmission(self):
        for text in ('CR1','CR 1','CR.2','CR-3','cruceta 1','cruceta 2','cruceta 3','Cardán CR2','Cardan cruceta 2'):
            with self.subTest(text=text):
                r=a.analyze(text);self.assertFalse(r['pendientes']);self.assertEqual(len(r['hallazgos']),1)
                self.assertEqual(r['hallazgos'][0]['componente'],'cruceta_direccion')
        for text in ('cruceta del cardán de transmisión','cruceta 2 de transmisión','cardan de transmisión CR2'):
            with self.subTest(text=text):
                r=a.analyze(text);self.assertFalse(r['pendientes']);self.assertEqual([f['componente'] for f in r['hallazgos']],['crucetas'])
        for text in ('CR4','amortiguador 9','PS5','A5 y 9','PF1.5','XR1','microcr2','3','5y6','larga derecha','sin juego en cruceta 2','no presenta fallas bloqueo'):
            with self.subTest(text=text):self.assertFalse(a.analyze(text)['hallazgos'])
        for text in ('tensor gira','PF1 desconocido pinchado','A1, pinchado, PF2'):
            with self.subTest(text=text):self.assertTrue(a.analyze(text)['pendientes'])
        self.assertEqual(a.analyze('cardan')['hallazgos'][0]['componente'],'cardan')
        self.assertEqual({f['referencia'] for f in a.analyze('A5 y A6 sueltos')['hallazgos']},{'a5','a6'})
        self.assertEqual(len(a.analyze('CR2 CR2')['hallazgos']),1)
        self.assertEqual(len(a.analyze('PF1 pinchado, CR2 con juego, A5-A6 sueltos')['hallazgos']),4)
        self.assertIsNone(a.analyze('pulmón de freno 1, pinchado')['hallazgos'][0]['subcomponente'])

    def test_old_engine_seven_report_is_verified_without_rewriting(self):
        fixture=fixtures.ReviewTests();fixture.setUp()
        try:
            data,report,detail=fixture.build(DICTIONARY);capsule=detail['novedades_sin_clasificar']['revision_mecanica']
            from _ftr_runtime.legacy_mechanics import mechanics
            events=[dict(r,fecha=date.fromisoformat(r['fecha'])) for r in capsule['registros']]
            capsule['motor_revision']=7;capsule['estadisticas']['anomalias']=mechanics(events,DICTIONARY,7)[0]
            before=copy.deepcopy(capsule);effect=review.preview(capsule,DICTIONARY)
            self.assertEqual(capsule,before);self.assertEqual((effect['motor_antes'],effect['motor_despues']),(7,8))
            review.unchanged_controls(capsule['estadisticas'],data)
        finally:fixture.tearDown()

    def test_two_periods_missing_column_and_unknowns_are_publishable(self):
        fixture=fixtures.ReviewTests();fixture.setUp()
        try:
            for year in (2024,2025):
                sheets=[fixture.sheet('Línea 999',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],[f'01/02/{year}','AA111AA',1,'SIN NOVEDAD','no coincide Kit'],[f'02/02/{year}','BB222BB',2,'OBSERVADO','CR2']])]
                data,_,detail=historical.build(sheets,year,'HISTORICAL_SOURCE_1234567','2026-10-23T20:00:00+00:00',DICTIONARY)
                stats.validate(data);self.assertEqual(data['totales']['registros_validos'],2)
                self.assertEqual((data['anomalias']['identificadas'],data['anomalias']['sin_clasificar']),(1,1))
                self.assertEqual(detail['novedades_sin_clasificar']['revision_mecanica']['periodo'],year)
            e=dict(fecha=date(2026,2,1),linea=999,dominio='AA111AA',estado='OBSERVADO',tiene_novedades=False,novedades='CR2')
            data,_=stats.mechanics([e]);self.assertEqual(data['estado'],'parcial');self.assertEqual(data['identificadas'],0)
        finally:fixture.tearDown()
