"""Confirmed terminology: synthetic observations, no source or publication I/O."""
import copy
import unittest
from _ftr_runtime import anomalies as engine, dictionary_rules as rules, public_statistics as stats
from _ftr_runtime.technical_fields import EXTRA_FIELDS

GENERAL=rules.compile_rules(dict(version=1,revision=4,reglas=[dict(expresion='extremo',variantes=['extremos'],tipo='descriptor',significado='extremo',alcance='general',habilitada=True)]))
CASES={
    'corta pitman': [('barra_corta','sin_ubicacion','lado pitman',None,'no_identificado',None)],
    'barra corta lado Pitman': [('barra_corta','sin_ubicacion','lado pitman',None,'no_identificado',None)],
    'barra corta lado eje': [('barra_corta','sin_ubicacion','lado eje',None,'no_identificado',None)],
    'Pulmón de freno trasero izquierdo diafragma': [('pulmon_freno','trasero izquierdo',None,'diafragma','no_identificado',None)],
    'pf1 y amortiguador 3': [('pulmon_freno','delantero izquierdo',None,None,'no_identificado',None),('amortiguadores','trasero izquierdo',None,None,'no_identificado',None)],
    'amortiguador 3 suleto': [('amortiguadores','trasero izquierdo',None,None,'suelto',None)],
    'flexible pulmón de freno delantero izquierdo, r3 lisa y amortiguador 3 suleto': [('flexibles_freno','delantero izquierdo',None,None,'no_identificado',None),('neumaticos_traseros','trasero izquierdo interno',None,None,'liso',None),('amortiguadores','trasero izquierdo',None,None,'suelto',None)],
    'barra estabilizadora y amortiguador de dirección, chicharra': [('barra_estabilizadora','sin_ubicacion',None,None,'no_identificado',None),('amortiguador_direccion','sin_ubicacion',None,None,'no_identificado',None),('sonora_marcha_atras','sin_ubicacion',None,None,'no_identificado',None)],
    'ambos neumáticos traseros internos cortados y barra corta lado Pitman con juego': [('neumaticos_traseros','trasero interno',None,None,'corte',2),('barra_corta','sin_ubicacion','lado pitman',None,'juego',None)],
    'barra corta delantero, r4, sistema de freno': [('barra_corta','delantero',None,None,'no_identificado',None),('neumaticos_traseros','trasero derecho interno',None,None,'no_identificado',None),('freno_sin_ubicacion','sin_ubicacion',None,None,'no_identificado',None)],
    'sistema freno trasera': [('freno_sin_ubicacion','trasero',None,None,'no_identificado',None)],
    'Carece de amortiguador delantero derecho': [('amortiguadores','delantero derecho',None,None,'faltante',None)],
    'A2 flojo': [('amortiguadores','delantero derecho',None,None,'flojo',None)],
    'A2 suelto': [('amortiguadores','delantero derecho',None,None,'suelto',None)],
    'R3 lisa': [('neumaticos_traseros','trasero izquierdo interno',None,None,'liso',None)],
    'No funciona chicharra marcha atrás': [('sonora_marcha_atras','sin_ubicacion',None,None,'no_funciona',None)],
    'No coincide Kit': [],
    'extremo barra larga': [('barra_larga','sin_ubicacion','extremo',None,'no_identificado',None)],
    'extremo barra corta': [('barra_corta','sin_ubicacion','extremo',None,'no_identificado',None)],
    'tensor extremo derecho': [('tensores','derecho','extremo',None,'no_identificado',None)],
}

class TechnicalV7Tests(unittest.TestCase):
    def test_required_cases_exact_attributes_pending_and_mentions(self):
        fields=('componente','ubicacion','parte','subcomponente','defecto','cantidad_fisica')
        for text,expected in CASES.items():
            with self.subTest(text=text):
                result=engine.analyze(text,GENERAL)
                self.assertCountEqual([tuple(f[k] for k in fields) for f in result['hallazgos']],expected)
                self.assertEqual(result['pendientes'],[text] if text=='No coincide Kit' else [])
                for finding in result['hallazgos']:
                    self.assertIn(finding['componente'],engine.CATEGORIES[finding['categoria']])
                if text.startswith('flexible'):
                    self.assertEqual(result['hallazgos'][0]['componente_asociado'],'pulmon_freno')

    def test_numbers_are_component_scoped_not_quantities(self):
        for text,ref,position in (('Amortiguador 3','a3','trasero izquierdo'),('Amortiguador.3','a3','trasero izquierdo'),
             ('Amortiguador-3','a3','trasero izquierdo'),('Pulmón de freno 1','pf1','delantero izquierdo'),
             ('Neumático 4','r4','trasero derecho interno'),('Pulmón de suspensión 2','ps2','delantero derecho'),
             ('R5','r5','trasero izquierdo externo'),('R6','r6','trasero derecho externo'),('R7','r7','trasero'),('A7','a7','sin_ubicacion')):
            with self.subTest(text=text):
                result=engine.analyze(text);self.assertFalse(result['pendientes'])
                self.assertEqual(len(result['hallazgos']),1)
                f=result['hallazgos'][0];self.assertEqual((f['referencia'],f['ubicacion'],f['cantidad_fisica']),(ref,position,None))
        for text in ('3','9','Amortiguador 9','Pulmón de suspensión 5','Pulmón de freno 7','Neumático 9','3.5','Amortiguador 3.5'):
            with self.subTest(text=text):
                self.assertFalse(engine.analyze(text)['hallazgos']);self.assertTrue(engine.analyze(text)['pendientes'])
        self.assertEqual(len(engine.analyze('R7 y R8')['hallazgos']),2)
        self.assertEqual(len(engine.analyze('A3 y A5')['hallazgos']),2)
        self.assertEqual(len(engine.analyze('PF3 y PF5')['hallazgos']),2)
        self.assertEqual(engine.analyze('Pulmón de freno.1')['hallazgos'][0]['referencia'],'pf1')
        separated=engine.analyze('Amortiguador, 3')
        self.assertEqual(separated['pendientes'],['3']);self.assertIsNone(separated['hallazgos'][0]['referencia'])
        self.assertFalse(engine.analyze('amortiguador3')['hallazgos'])

    def test_meaning_boundaries_and_original_state_are_preserved(self):
        from datetime import date
        text=list(CASES)[8]
        event=dict(fecha=date(2026,1,1),linea=999,dominio='AA111AA',interno=1,estado='SIN NOVEDAD',estado_original='SIN NOVEDAD',tiene_novedades=True,novedades=text)
        before=copy.deepcopy(event)
        aggregate,_=stats.mechanics([event])
        self.assertEqual(event,before);self.assertEqual(aggregate['identificadas'],2)
        self.assertEqual(aggregate['cobertura']['registros_validos'],1)
        self.assertEqual(aggregate['elementos_fisicos'],dict(cantidad_confirmada=2,menciones_con_cantidad=1,menciones_sin_cantidad=1))
        self.assertEqual(sum(c['estados']['sin_novedad'] for cat in aggregate['categorias'] for c in cat['componentes']),2)
        for text in ('corta','extremo','diafragma','suleto','sistema','sin fallas amortiguador','no presenta problemas pulmón de freno','posible corta pitman','no coincide Kit'):
            with self.subTest(text=text):self.assertFalse(engine.analyze(text,GENERAL)['hallazgos'])
        self.assertEqual(engine.analyze('brazo Pitman')['hallazgos'][0]['componente'],'brazo_pitman')
        self.assertTrue(engine.analyze('diafragma tensor')['pendientes'])
        result=engine.analyze('barra corta ambos extremos con juego',GENERAL)
        self.assertEqual(len(result['hallazgos']),1)
        self.assertIsNone(result['hallazgos'][0]['cantidad_fisica'])
        result=engine.analyze('tensor y no funciona chicharra')
        by_component={f['componente']:f for f in result['hallazgos']}
        self.assertEqual(by_component['tensores']['defecto'],'no_identificado')
        self.assertEqual(by_component['sonora_marcha_atras']['defecto'],'no_funciona')

    def test_typed_rules_and_explicit_correction_precedence(self):
        row=dict(expresion='diafragma',tipo='descriptor',informacion='subcomponente',significado='diafragma',categoria='frenos',componente='pulmon_freno',habilitada=True)
        d=rules.validate(dict(version=1,revision=1,reglas=[row]))
        self.assertEqual(engine.analyze('PF1 diafragma',rules.compile_rules(d))['hallazgos'][0]['subcomponente'],'diafragma')
        for changes in (dict(significado='extremo'),dict(componente='barra_corta',categoria='direccion'),dict(informacion='ubicacion')):
            with self.assertRaises(ValueError):rules.validate(dict(d,reglas=[dict(row,**changes)]))
        correction=dict(expresion='brazo pitman',tipo='correccion',categoria='direccion',componente='barra_corta',parte='lado pitman',habilitada=True)
        d=rules.validate(dict(version=1,revision=1,reglas=[correction]))
        result=engine.analyze('brazo pitman con juego',rules.compile_rules(d))
        self.assertEqual(len(result['hallazgos']),1);self.assertEqual(result['hallazgos'][0]['componente'],'barra_corta')
        self.assertEqual(result['hallazgos'][0]['parte'],'lado pitman')

if __name__=='__main__':unittest.main()
