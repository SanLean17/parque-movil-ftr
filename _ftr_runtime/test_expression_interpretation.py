"""Contrato de frases FTR confirmado por el usuario; todos los datos son ficticios."""
import copy
import json
import unittest
from datetime import date
from _ftr_runtime import anomalies as engine, dictionary_rules as rules, public_statistics as stats, mechanical_review
from _ftr_runtime.test_public_statistics import StatisticsPipelineTests


class ExpressionTests(unittest.TestCase):
    def check(self,text,components,unknown=()):
        result=engine.analyze(text)
        self.assertCountEqual([f['componente'] for f in result['hallazgos']],components)
        self.assertEqual(result['pendientes'],list(unknown))
        for finding in result['hallazgos']:
            self.assertEqual(finding['categoria'],engine.OWNER[finding['componente']])
        return result

    def test_required_complete_expressions(self):
        cases=[
            ('BARRA CORTA TRAS, TENSOR ISK',['barra_corta','tensores']),
            ('CORTA ENTERA',['barra_corta']),('CORTA DELANTERO',['barra_corta']),
            ('TENSOR DER MONIO DEL',['tensores']),('TENSOR SUP',['tensores']),
            ('PF1',['pulmon_freno']),('PF.1',['pulmon_freno']),('PF 3',['pulmon_freno']),
            ('P.F.4',['pulmon_freno']),('BARRA LARGA, PF.3',['barra_larga','pulmon_freno']),
            ('PS1',['pulmon_suspension']),('PS.1',['pulmon_suspension']),('PS 4',['pulmon_suspension']),
            ('A2 SUELTO',['amortiguadores']),('A.4 FLOJO',['amortiguadores']),('A6 SUELTO',['amortiguadores']),
            ('A4 BUJE FLOJO',['bujes']),('FLEXIBLE DE FRENO ZONA MEDIA',['flexibles_freno']),
            ('R1 CORTADO, A2 SUELTO, PF.3, CHICHARRA',['neumaticos_delanteros','amortiguadores','pulmon_freno','sonora_marcha_atras'])]
        for text,expected in cases:
            with self.subTest(text=text):self.check(text,expected)

    def test_code_variants_bounded_and_distinct(self):
        for prefix,last,component in (('PF',6,'pulmon_freno'),('PS',4,'pulmon_suspension'),('A',8,'amortiguadores'),('R',8,None)):
            for number in range(1,last+1):
                forms=[f'{prefix}{number}',f'{prefix} {number}',f'{prefix}.{number}',f'{prefix},{number}',f'{prefix}.  {number}']
                if len(prefix)==2:forms += [f'{prefix[0]}.{prefix[1]}.{number}',f'{prefix[0]} {prefix[1]} {number}']
                for text in forms:
                    with self.subTest(text=text):
                        expected=component or ('neumaticos_delanteros' if number<=2 else 'neumaticos_traseros')
                        finding=self.check(text,[expected])['hallazgos'][0]
                        self.assertEqual(finding['referencia'],prefix.lower()+str(number))
                        if prefix=='A' and number>6:self.assertEqual(finding['ubicacion'],'sin_ubicacion')
                        elif number>2:
                            self.assertTrue(finding['ubicacion'].startswith('trasero'))
                            self.assertNotIn('interior',finding['ubicacion']);self.assertNotIn('exterior',finding['ubicacion'])
                        else:self.assertEqual(finding['ubicacion'],'delantero izquierdo' if number==1 else 'delantero derecho')
        self.check('A7 A8 A7',['amortiguadores','amortiguadores'])
        self.check('PF1 PS1',['pulmon_freno','pulmon_suspension'])
        for text in ('PULMÓN DEL FRENO','BUJE DEL AMORTIGUADOR'):
            self.assertEqual(engine.analyze(text)['hallazgos'][0]['ubicacion'],'sin_ubicacion')
        for text in ('PF7','PS5','A9','R9','PF.33','PS 10','A 12','PF3ABC','XR1','A2B','A2.1','PF3.4','PS1,2'):
            with self.subTest(text=text):self.check(text,[],[text])
        # Ni una palabra intermedia ni un salto de línea fabrican un código.
        self.check('P texto F 3',[],['P texto F 3'])
        self.check('P\nF 3',[],['P','F 3'])

    def test_associated_descriptions_not_global_stop_words(self):
        cases={'BARRA CORTA TRAS, TENSOR ISK':{'TRAS','ISK'},'A2 SUELTO':{'SUELTO'},
               'FLEXIBLE DE FRENO ZONA MEDIA':{'ZONA MEDIA'},'TENSOR DER MONIO DEL':{'DER','MONIO','DEL'}}
        for text,expected in cases.items():
            with self.subTest(text=text):
                result=engine.analyze(text)
                self.assertFalse(result['pendientes']);self.assertEqual({d['texto'] for d in result['descriptores']},expected)
        for text in ('ISK','DER','IZQ','TRAS','DEL','SUP','SUELTO','FLOJO','ENTERA','MOÑO','MONIO','ZONA MEDIA'):
            with self.subTest(text=text):self.check(text,[],[text])
        self.check('TENSOR DESCONOCIDO SUP',['tensores'],['DESCONOCIDO SUP'])
        self.check('A2 SUELTO, MONIO',['amortiguadores'],['MONIO'])
        self.check('CARDAN MONIO',['cardan'],['MONIO'])
        for text in ('JUEGO DEL AMORTIGUADOR','TENSOR DEL MOÑO'):
            self.assertEqual(engine.analyze(text)['hallazgos'][0]['ubicacion'],'sin_ubicacion')
        result=self.check('FRENOS DEL SISTEMA DESCONOCIDO',['freno_sin_ubicacion'],['SISTEMA DESCONOCIDO'])
        self.assertEqual(result['hallazgos'][0]['ubicacion'],'sin_ubicacion')

    def test_bars_and_tensor_context(self):
        for text in ('Barra corta tras.','Barra corta delantero','Barra corta lado Pitman','Barra corta lado eje','Barra corta entera','Juego barra corta'):
            with self.subTest(text=text):self.check(text,['barra_corta'])
        for text in ('Barra larga derecha','Barra larga izquierda','Barra larga lado rueda'):
            with self.subTest(text=text):self.check(text,['barra_larga'])
        self.check('BARRA CORTA TRAS; BARRA CORTA ENTERA',['barra_corta'])
        self.check('BARRA CORTA, BRAZO PITMAN',['barra_corta','brazo_pitman'])
        for text in ('Tensor izquierdo','Tensor der.','Tensor izq.','Tensor sup.','Tensor delantero','Tensor trasero','Tensor superior moño trasero'):
            with self.subTest(text=text):self.check(text,['tensores'])
        for text in ('CORTA','CORREA CORTA ENTERA','TENSOR DE DIRECCIÓN'):
            with self.subTest(text=text):self.check(text,[],[text])
        for text in ('PS1 DE FRENO','PF1 DE SUSPENSIÓN','TENSOR SUP DE DIRECCIÓN'):
            with self.subTest(text=text):self.check(text,[],[text])
        self.check('PS1 Y FRENOS CON JUEGO',['pulmon_suspension','freno_sin_ubicacion'])
        self.check('A2 DIRECCIÓN FLOJA',['amortiguadores','direccion_sin_componente'])
        self.check('CARDAN SUSPENSIÓN TRASERA',['cardan','suspension_sin_componente'])

    def test_losses_do_not_invent_a_brake_component(self):
        for text in ('PÉRDIDA DE AIRE ZONA DELANTERA','PERDIDA AIRE','PÉRDIDA DE AIRE ZONA MEDIA','PÉRDIDA DE AIRE ZONA TRASERA'):
            with self.subTest(text=text):self.check(text,[],[text])
        for text in ('FRENOS CON PERDIDA DE AIRE ZONA MEDIA','PERDIDA DE AIRE EN FRENOS','PERDIDA DE AIRE EN EL SISTEMA DE FRENOS'):
            with self.subTest(text=text):self.check(text,['freno_sin_ubicacion'])
        self.check('BARRA CORTA, PÉRDIDA DE AIRE, CHICHARRA NO FUNCIONA',['barra_corta','sonora_marcha_atras'],['PÉRDIDA DE AIRE'])
        for text in ('FLEXIBLE DE COMBUSTIBLE','FLEXIBLE DE SUSPENSIÓN','FLEXIBLE DE AGUA'):
            with self.subTest(text=text):self.check(text,[],[text])

    def test_separators_negations_duplicates_and_unknowns(self):
        for sep in (', ','. ','; ',' - ',' — ','\n',' y ',' '):
            text=sep.join(('R1 CORTADO','A2 SUELTO','PF.3','CHICHARRA'))
            with self.subTest(sep=sep):self.check(text,['neumaticos_delanteros','amortiguadores','pulmon_freno','sonora_marcha_atras'])
        self.check('1. PF.3 2. PS.1 3. A.2',['pulmon_freno','pulmon_suspension','amortiguadores'])
        self.check('PF.3, PF 3, P.F.3',['pulmon_freno'])
        self.check('A4 BUJE FLOJO',['bujes'])
        self.check('A4 ROTO Y BUJE DE A4 FLOJO',['amortiguadores','bujes'])
        self.check('A2 SUELTO, EXPRESIÓN DESCONOCIDA, PS.1',['amortiguadores','pulmon_suspension'],['EXPRESIÓN DESCONOCIDA'])
        for text in ('PF.3 SIN FALLAS','POSIBLE PS.1','NO PRESENTA FALLA DE A2 Y PF.3','A2 SIN JUEGO','PS.1?','NO SE OBSERVAN FALLAS EN PF.3','NO HAY JUEGO EN A2'):
            with self.subTest(text=text):self.check(text,[],[text])
        self.check('A2 SIN JUEGO, PF.3',['pulmon_freno'],['A2 SIN JUEGO'])

    def test_reserved_codes_all_years_and_old_reports(self):
        for text in ('PF','PF7','PS','PS5','A7','A9','R9'):
            with self.subTest(text=text),self.assertRaises(ValueError):rules.expression(text)
        value=rules.proposed(rules.EMPTY,[dict(expresion='xyz',categoria='suspension',componente='tensores',habilitada=True)],rules.digest(rules.EMPTY))
        for year in (2025,2026,2027,2028):
            event=dict(fecha=date(year,1,1),estado='OBSERVADO',tiene_novedades=True,novedades='PS.1 XYZ')
            before=copy.deepcopy(event)
            data,_=stats.mechanics([event],dictionary=json.loads(rules.encoded(value)))
            self.assertEqual(data['identificadas'],2);self.assertEqual(event,before)
        with self.assertRaisesRegex(ValueError,'motor anterior'):mechanical_review.unpack({'version':1})


class ExpressionPipelineTests(unittest.TestCase):
    setUp=StatisticsPipelineTests.setUp
    tearDown=StatisticsPipelineTests.tearDown
    sheet=StatisticsPipelineTests.sheet
    google=StatisticsPipelineTests.google
    read=StatisticsPipelineTests.read

    def test_original_controls_states_and_archives_preserved(self):
        rows=[['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
              ['01/01/2026',36,'AA111AA',1,'OBSERVADO','A2 FLOJO'],
              ['02/01/2026',36,'AA111AA',1,'FUERA DE SERVICIO','A2 SUELTO'],
              ['03/01/2026',37,'CC333CC',2,'SIN NOVEDAD','R1 CORTADO, A2 SUELTO, PF.3, CHICHARRA']]
        original=copy.deepcopy(rows)
        self.google([self.sheet('LINEA 36/37',rows)]);data=self.read()
        self.assertEqual(rows,original)
        self.assertEqual(data['totales']['registros_validos'],3)
        self.assertEqual(data['totales']['unidades_unicas_por_linea'],2)
        self.assertEqual(data['totales']['unidades_repetidas'],1)
        self.assertEqual(data['anomalias']['identificadas'],6)
        self.assertEqual(data['anomalias']['sin_clasificar'],0)
        component=next(c for cat in data['anomalias']['categorias'] for c in cat['componentes'] if c['id']=='amortiguadores')
        self.assertEqual([component['estados'][s] for s in ('fuera_de_servicio','observado','sin_novedad')],[1,1,1])
        self.assertEqual(engine.analyze('A2 FLOJO')['hallazgos'][0]['defecto'],'flojo')
        self.assertEqual(engine.analyze('A2 SUELTO')['hallazgos'][0]['defecto'],'suelto')
        for private in ('SUELTO','FLOJO','AA111AA','CC333CC','descriptores'):
            self.assertNotIn(private,json.dumps(data))
