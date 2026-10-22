"""Estadísticas públicas sobre visitas ficticias. Nunca consulta fuentes reales."""
import copy
import json
import unittest
from unittest.mock import patch
from _ftr_runtime import anomalies, public_statistics as stats, worker
from _ftr_runtime import test_source_pipeline as fixtures
admin=fixtures.admin


class MechanicalTests(unittest.TestCase):
    def test_multiple_components_and_positions(self):
        known, unknown=anomalies.classify('Amortiguador delantero derecho, suspensión trasera izquierda y freno trasero derecho')
        self.assertEqual([x[1] for x in known],['frenos_traseros','amortiguadores','suspension_sin_componente'])
        self.assertEqual(unknown,[])
        known,_=anomalies.classify('Amortiguadores delanteros derecho e izquierdo; frenos delanteros y traseros')
        self.assertEqual(len(known),4)
        self.assertEqual({x[1] for x in known},{'amortiguadores','frenos_delanteros','frenos_traseros'})
        known,_=anomalies.classify('frenos delanteros derecho e izquierdo')
        self.assertEqual([x[1] for x in known],['frenos_delanteros','frenos_delanteros'])

    def test_known_unknown_can_coexist_without_inventing_codes(self):
        for value in ('Barra larga, R3','R1 R2 R3 y barra corta','Cardán; abreviatura desconocida'):
            with self.subTest(value=value):
                known, unknown=anomalies.classify(value)
                self.assertEqual(len(known),1)
                self.assertTrue(unknown)
        known,unknown=anomalies.classify('R3')
        self.assertFalse(known);self.assertEqual(unknown,['r3'])

    def test_no_substring_or_unqualified_flexible_equivalence(self):
        for value in ('refrenos','cardanico','barrita','flexible','amortiguadorXYZ','frenos? quizá otro componente','dirección del domicilio','suspensión de la visita'):
            with self.subTest(value=value):
                known,unknown=anomalies.classify(value)
                self.assertFalse(known);self.assertTrue(unknown)

    def test_no_normality_or_negation_becomes_confirmed_anomaly(self):
        for value in ('Sin novedad','SIN NOVEDADES','Frenos sin fallas','dirección en buen estado','no presenta falla de cardán','frenos OK'):
            with self.subTest(value=value):self.assertFalse(anomalies.classify(value)[0])

    def test_repeated_keywords_do_not_duplicate_one_finding(self):
        known,unknown=anomalies.classify('Flexible de freno delantero derecho; flexible de freno delantero derecho')
        self.assertEqual(len(known),1);self.assertFalse(unknown)
        known,_=anomalies.classify('Amortiguador delantero derecho; amortiguador delantera derecha')
        self.assertEqual(len(known),1)

    def test_catalogue_categories_and_accents(self):
        known,unknown=anomalies.classify('barra larga, barra corta, flexibles de freno, bujes, cardán, crucetas')
        self.assertEqual({x[0] for x in known},{'direccion','frenos','suspension','transmision'})
        self.assertEqual(len(known),6);self.assertFalse(unknown)


class StatisticsPipelineTests(unittest.TestCase):
    setUp=fixtures.SourcePipelineTests.setUp
    tearDown=fixtures.SourcePipelineTests.tearDown
    sheet=fixtures.SourcePipelineTests.sheet
    sheets=fixtures.SourcePipelineTests.sheets
    google=fixtures.SourcePipelineTests.google

    def read(self):return json.loads((self.root/stats.FILE).read_text(encoding='utf-8'))

    def visits(self):
        return [self.sheet('Línea 36/37',[
            ['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
            ['01/01/2026',36,'AA111AA',1,'FUERA DE SERVICIO','barra larga, freno trasero derecho, R3'],
            ['02/02/2026',36,'AA111AA',1,'OBSERVADO','cardán y crucetas'],
            ['03/02/2026',36,'AA111AA',1,'SIN NOVEDAD','sin novedad'],
            ['01/03/2026',37,'CC333CC',8,'','amortiguador delantero derecho'],
        ])]

    def test_six_indicators_months_and_no_fleet_filter(self):
        self.google(self.visits());data=self.read()
        self.assertEqual(data['totales'],dict(registros_validos=4,unidades_unicas_por_linea=2,unidades_repetidas=1,registros_fuera_de_servicio=1,registros_observados=1,registros_sin_novedad=1,registros_sin_estado=1,registros_otro_estado=0))
        self.assertEqual([m['controles'] for m in data['mensual']], [1,2,1]+[0]*9)
        self.assertEqual([m['estado'] for m in data['mensual']][-3:],['en_curso','futuro','futuro'])
        self.assertEqual(data['anomalias']['identificadas'],5)
        self.assertEqual(data['anomalias']['sin_clasificar'],1)
        self.assertEqual(data['totales']['registros_validos'],4)
        self.assertEqual(data['anomalias']['categorias'][1]['componentes'][1]['estados']['fuera_de_servicio'],1)

    def test_original_admin_statistics_unchanged_when_novedades_enabled(self):
        sheets=self.visits();self.google(sheets)
        report=json.loads((self.root/'reports/resumen.json').read_text())
        base,records=admin.base.analyze(sheets,{36:9999,37:9999},2026,self.clock.date())
        admin.base.add_comparison(base,records,self.root)
        admin.extend_report(base,sheets,self.root,{36:9999,37:9999},'fake',self.clock.isoformat(),today=self.clock.date())
        from _ftr_admin.estadisticas_periodo import completar_estadisticas
        completar_estadisticas(base,admin.source_rows(sheets),self.clock.date())
        self.assertEqual(base['totales_estadisticas'],report['totales_estadisticas'])
        for key in stats.LINE_FIELDS:
            self.assertEqual([r[key] for r in base['estadisticas']], [r[key] for r in report['estadisticas']])

    def test_optional_header_moves_and_horizontal_vertical_tables_never_mix(self):
        horizontal=self.sheet('LINEA 36/37',[
            ['LINEA 36','','','','','','LINEA 37'],
            ['FECHA','DOMINIO','INTERNO','NOVEDADES','ESTADO','','FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
            ['01/01/2026','AA111AA',1,'barra corta','OBSERVADO','','02/02/2026','BB222BB',1,'FUERA DE SERVICIO','cardán'],
            ['', 'LINEA 36'],
            ['NOVEDADES','FECHA','DOMINIO','INTERNO','ESTADO'],
            ['R3','03/03/2026','AA111AA',1,'SIN NOVEDAD']])
        self.google([horizontal])
        rows=list(admin.source_rows([horizontal],include_novedades=True))
        self.assertEqual([(r['linea'],r['novedades']) for r in rows],[(36,'barra corta'),(37,'cardán'),(36,'R3')])
        self.assertEqual(self.read()['anomalias']['identificadas'],2)
        self.assertEqual(self.read()['anomalias']['sin_clasificar'],1)

    def test_missing_or_duplicate_novedades_reports_incomplete_coverage(self):
        for headers in (['FECHA','DOMINIO','INTERNO'],['FECHA','DOMINIO','INTERNO','NOVEDADES','NOVEDADES']):
            with self.subTest(headers=headers):
                sheets=[self.sheet('LINEA 36',[headers,['01/01/2026','AA111AA',1,'barra larga','cardan']]),self.sheet('LINEA 37',[['FECHA','DOMINIO','INTERNO','NOVEDADES'],['01/01/2026','BB222BB',1,'']])]
                self.google(sheets);data=self.read()['anomalias']
                self.assertEqual(data['estado'],'parcial')
                self.assertEqual(data['cobertura'],dict(registros_validos=2,con_columna=1,con_texto=0,vacios=1,sin_columna=1))
                self.assertEqual(data['identificadas'],0)

    def test_adjacent_tables_do_not_share_one_novedades_column(self):
        table=self.sheet('LINEA 36/37',[
            ['LINEA 36','','','','LINEA 37'],
            ['FECHA','DOMINIO','INTERNO','NOVEDADES','FECHA','DOMINIO','INTERNO'],
            ['01/01/2026','AA111AA',1,'cardán','01/01/2026','BB222BB',1]])
        self.google([table]);data=self.read()['anomalias']
        self.assertEqual(data['identificadas'],1)
        self.assertEqual(data['cobertura']['sin_columna'],1)
        self.assertEqual(data['estado'],'parcial')

    def test_auxiliary_other_year_and_disabled_lines_are_excluded(self):
        sheets=self.visits()+[self.sheet('Resumen Línea 36',[['FECHA','LINEA','DOMINIO','INTERNO','NOVEDADES'],['01/01/2026',36,'XX999XX',1,'cardan']])]
        sheets[0].cells.update({(6,1):'01/01/2025',(6,2):36,(6,3):'AA111AA',(6,4):1,(6,6):'cardan'})
        self.google(sheets);self.assertEqual(self.read()['anomalias']['identificadas'],5)

    def test_failed_read_preserves_last_valid_statistics(self):
        self.google(self.visits());before=(self.root/stats.FILE).read_bytes()
        sheets=self.visits();sheets[0].cells[2,3]='INVALIDO'
        with self.assertRaises(ValueError):self.google(sheets)
        self.assertEqual((self.root/stats.FILE).read_bytes(),before)

    def test_public_projection_never_contains_private_text_or_identifiers(self):
        sheets=self.visits();sheets[0].cells[2,6]='barra larga; CANARIO_PRIVADO inspector nombre dirección R3'
        with patch.object(admin,'seal',wraps=admin.seal) as seal:self.google(sheets)
        public=(self.root/stats.FILE).read_text();summary=(self.root/'reports/resumen.json').read_text()
        for forbidden in ('CANARIO_PRIVADO','AA111AA','CC333CC','inspector nombre','pestana_posicion','expresiones','wrapped_key'):
            self.assertNotIn(forbidden,public)
        self.assertNotIn('CANARIO_PRIVADO',summary)
        self.assertIn('canario_privado',json.dumps(seal.call_args.args[0]['novedades_sin_clasificar']))
        corrupted=self.read();corrupted['novedades']='CANARIO_PRIVADO'
        with self.assertRaises(ValueError):stats.validate(corrupted)

    def test_integrity_includes_statistics_and_rejects_incompatible_data(self):
        self.google(self.visits());data=self.read()
        self.assertIn(stats.FILE,worker.public_hashes(self.root,self.config))
        for mutate in (lambda d:d['mensual'][0].update(controles=99),lambda d:d.update(periodo=0),lambda d:d['totales'].update(unidades_repetidas=20),lambda d:d['anomalias']['categorias'][0].update(id='TEXTO_PRIVADO')):
            with self.subTest(mutate=mutate):
                bad=copy.deepcopy(data);mutate(bad)
                with self.assertRaises(ValueError):stats.validate(bad)

    def test_rankings_ties_small_samples_and_zero_denominator(self):
        lines=[dict(linea=1,registros_periodo=100,fuera_de_servicio=15,observado=0),dict(linea=2,registros_periodo=20,fuera_de_servicio=10,observado=2),dict(linea=3,registros_periodo=1,fuera_de_servicio=1,observado=0),dict(linea=4,registros_periodo=0,fuera_de_servicio=0,observado=0)]
        ratios=stats.proportions(lines)
        self.assertEqual([r['linea'] for r in ratios],[3,2,1,4])
        self.assertFalse(ratios[0]['muestra_suficiente']);self.assertEqual(ratios[1]['porcentaje'],50)
        self.assertIsNone(ratios[-1]['porcentaje'])
        self.assertEqual(stats.proportions([dict(linea=1,registros_periodo=80,fuera_de_servicio=1)])[0]['porcentaje'],1.3)
        lines[1]['fuera_de_servicio']=15
        self.assertEqual(stats.ranking(lines)['fuera_de_servicio'],dict(cantidad=15,lineas=[1,2]))
        lines[1]['fuera_de_servicio']=16
        self.assertEqual(stats.ranking(lines)['fuera_de_servicio']['lineas'],[2])

    def test_empty_period_valid_and_pending_is_never_zero(self):
        self.config['period']=2027;self.google(self.visits());data=self.read()
        self.assertEqual(data['totales']['registros_validos'],0)
        self.assertTrue(all(m['estado']=='futuro' for m in data['mensual']))
        pending,_=stats.mechanics([],pending=True)
        self.assertIsNone(pending['identificadas']);self.assertIsNone(pending['categorias'][0]['cantidad'])
