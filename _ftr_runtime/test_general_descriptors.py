"""Descriptores generales: fuentes ficticias, sin escrituras ni lecturas remotas."""
import copy
import json
import unittest
from _ftr_runtime import anomalies as a, dictionary_rules as rules, mechanical_review as review, record_interpretation as records
from _ftr_runtime import test_mechanical_review as fixtures

CASES={
    'EXTREMO BARRA LARGA':['barra_larga'],
    'EXTREMO BARRA CORTA':['barra_corta'],
    'TENSOR EXTREMO DERECHO':['tensores'],
    'EXTREMOS BARRA LARGA - CRUCETA 2':['barra_larga','crucetas'],
    'EXTREMO DELANTERO DE BARRA CORTA':['barra_corta'],
    'BARRA LARGA, EXTREMO IZQUIERDO CON JUEGO':['barra_larga'],
}

def descriptor(**changes):
    return dict(dict(expresion='EXTREMO',variantes=['EXTREMOS'],tipo='descriptor',significado='extremo',alcance='general',habilitada=True),**changes)

def dictionary(*rows):return rules.validate(dict(version=1,revision=2,reglas=list(rows) or [descriptor()]))

class GeneralDescriptorTests(unittest.TestCase):
    def test_required_cases_with_exact_components_and_no_extra_anomaly(self):
        compiled=rules.compile_rules(dictionary())
        for text,components in CASES.items():
            with self.subTest(text=text):
                value=a.analyze(text,compiled)
                self.assertEqual(sorted(f['componente'] for f in value['hallazgos']),components)
                self.assertEqual(len(value['hallazgos']),len(a.analyze(text)['hallazgos']))
                # El 2 de CRUCETA 2 conserva su revisión anterior: no se inventa un código.
                self.assertEqual(value['pendientes'],['2'] if 'CRUCETA 2' in text else [])
                self.assertTrue(any(d['texto'].startswith('EXTREMO') for d in value['descriptores']))
        self.assertEqual(a.analyze('EXTREMO',compiled),dict(hallazgos=[],pendientes=['EXTREMO'],descriptores=[]))

    def test_boundaries_unknown_words_and_ambiguity_are_not_hidden(self):
        compiled=rules.compile_rules(dictionary())
        for text in ('EXTREMOS','BARRA LARGA EXTREMO BARRA CORTA','BARRA LARGA, EXTREMO, BARRA CORTA',
                     'BARRA LARGA Y TENSOR, EXTREMO','EXTREMO, BARRA LARGA','BARRA LARGA; EXTREMO',
                     'TENSOR DERECHO Y TENSOR IZQUIERDO, EXTREMO',
                     'BARRA LARGA - EXTREMO','BARRA LARGA. EXTREMO','BARRA LARGA\nEXTREMO',
                     'BARRA LARGA DESCONOCIDO EXTREMO','EXTREMO DESCONOCIDO TENSOR','BARRA LARGA, EXTREMO DESCONOCIDO',
                     'TENSOR POSIBLE EXTREMO','SIN JUEGO TENSOR EXTREMO','R99 EXTREMO','MOTOR EXTREMO','DIRECCION EXTREMO'):
            with self.subTest(text=text):
                value=a.analyze(text,compiled)
                self.assertTrue(any('EXTREMO' in p for p in value['pendientes']),value)
                self.assertFalse(any('EXTREMO' in d['texto'] for d in value['descriptores']))
        value=a.analyze('BARRA LARGA Y EXTREMO BARRA CORTA',compiled)
        self.assertEqual(value['pendientes'],[])
        self.assertEqual([d['componente'] for d in value['descriptores'] if d['texto']=='EXTREMO'],['barra_corta'])
        self.assertEqual(a.analyze('EXTREMOSA BARRA LARGA',compiled)['pendientes'],['EXTREMOSA'])
        self.assertEqual(len(a.analyze('EXTREMO BARRA LARGA; EXTREMOS BARRA LARGA',compiled)['hallazgos']),1)
        text='TENSOR EXTREMO DERECHO; TENSOR EXTREMO IZQUIERDO'
        result=a.analyze(text,compiled)
        self.assertEqual(result['hallazgos'],a.analyze(text)['hallazgos'])
        self.assertTrue(result['pendientes'])

    def test_general_location_words_only_in_unambiguous_contexts(self):
        for word in ('DERECHO','IZQUIERDO','SUPERIOR','INFERIOR'):
            compiled=rules.compile_rules(dictionary(descriptor(expresion=word,significado=word.lower(),variantes=[])))
            for text in (word+' TENSOR','TENSOR '+word,'TENSOR, '+word):
                with self.subTest(text=text):
                    result=a.analyze(text,compiled)
                    self.assertEqual(len(result['hallazgos']),1)
                    self.assertEqual(result['hallazgos'][0]['ubicacion'],word.lower())
                    self.assertEqual(result['pendientes'],[])
            for text in (word,'TENSOR '+word+' AMORTIGUADOR','TENSOR, '+word+', AMORTIGUADOR'):
                self.assertIn(word,a.analyze(text,compiled)['pendientes'])

    def test_specific_precedence_and_disabled_specific_fallback(self):
        specific=dict(expresion='EXTREMO',categoria='suspension',componente='tensores',tipo='descriptor',significado='superior',habilitada=True)
        d=dictionary(descriptor(),specific);compiled=rules.compile_rules(d)
        self.assertEqual(a.analyze('TENSOR EXTREMO',compiled)['hallazgos'][0]['ubicacion'],'superior')
        self.assertEqual(a.analyze('TENSOR, EXTREMO',compiled)['hallazgos'][0]['ubicacion'],'superior')
        self.assertEqual(a.analyze('TENSOR, EXTREMO',compiled)['pendientes'],[])
        self.assertEqual(a.analyze('AMORTIGUADOR EXTREMO',compiled)['pendientes'],[])
        specific['habilitada']=False
        self.assertEqual(a.analyze('TENSOR EXTREMO',rules.compile_rules(dictionary(descriptor(),specific)))['hallazgos'][0]['ubicacion'],'sin_ubicacion')
        # La ausencia de alcance/variantes sigue produciendo los mismos bytes.
        old=dict(version=1,revision=1,reglas=[dict(specific,expresion='extremo')])
        self.assertEqual(rules.encoded(old),(json.dumps(old,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())

    def test_schema_variants_conflicts_and_closed_vocabulary(self):
        self.assertEqual(dictionary(descriptor(variantes=['EXTREMO','EXTREMOS']))['reglas'][0]['variantes'],['extremos'])
        for changed in (dict(alcance='todo'),dict(componente='barra_larga'),dict(categoria='direccion'),dict(variantes='EXTREMOS'),
                        dict(variantes=['extremos','EXTREMOS']),dict(variantes=['palabra desconocida']),dict(expresion='CUALQUIER'),
                        dict(variantes=['AA111AA']),dict(variantes=['<script>']),dict(variantes=['extremo']*9)):
            with self.subTest(changed=changed),self.assertRaises(ValueError):dictionary(descriptor(**changed))
        for other in (descriptor(),descriptor(expresion='extremos',variantes=[])):
            with self.assertRaises(ValueError):dictionary(descriptor(),other)
        row=descriptor(alcance='componente',categoria='direccion',componente='barra_larga')
        with self.assertRaises(ValueError):dictionary(row,dict(row,expresion='extremos',variantes=[]))

    def test_private_fragments_keep_original_positions_and_explicit_boundaries(self):
        text='BARRA LARGA, EXTREMO IZQUIERDO CON JUEGO';d=dictionary()
        fragments=records.suggestions(text,d)
        self.assertEqual(len(fragments),1)
        self.assertEqual(records.interpret(text,fragments,d),a.analyze(text,rules.compile_rules(d)))
        # Si el usuario divide explícitamente, no se atraviesa su decisión.
        split=records.suggestions(text,rules.EMPTY)
        self.assertTrue(records.interpret(text,split,d)['pendientes'])

class GeneralPreviewTests(unittest.TestCase):
    setUp=fixtures.ReviewTests.setUp
    tearDown=fixtures.ReviewTests.tearDown
    sheet=fixtures.ReviewTests.sheet
    build=fixtures.ReviewTests.build
    def source(self):
        texts=[*CASES,'EXTREMO','BARRA LARGA EXTREMO BARRA CORTA','EXTREMO BARRA LARGA; EXTREMOS']
        return [self.sheet('Línea 999',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
            *[['01/02/2025','AA111AA',7,'OBSERVADO' if i%2 else 'FUERA DE SERVICIO',text] for i,text in enumerate(texts)]])]

    def test_complete_preview_partial_ambiguity_controls_and_legacy_snapshot(self):
        data,_,detail=self.build();snap=detail['novedades_sin_clasificar']['revision_mecanica'];snap['motor_revision']=5
        before=copy.deepcopy(snap);effect=review.preview(snap,dictionary())
        self.assertEqual(effect['registros'],9)
        self.assertEqual(effect['antes']['sin_clasificar']-effect['despues']['sin_clasificar'],7)
        self.assertEqual(effect['antes']['identificadas'],effect['despues']['identificadas'])
        self.assertEqual(len(effect['afectados']),7)
        self.assertEqual(len(effect['ambiguos']),3)
        self.assertTrue(set(r['registro_id'] for r in effect['afectados'])&set(r['registro_id'] for r in effect['ambiguos']))
        for category in effect['antes']['categorias']:
            if category['id']!='otras':self.assertEqual(category,next(c for c in effect['despues']['categorias'] if c['id']==category['id']))
        after=copy.deepcopy(data);after['anomalias']=effect['despues'];review.unchanged_controls(data,after)
        self.assertEqual(snap,before)
        snap['estadisticas']['anomalias']['sin_clasificar']+=1
        with self.assertRaises(ValueError):review.preview(snap,dictionary())
