"""V2: equivalencias autorizadas, días, privacidad y conservación entre años."""
import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from _ftr_runtime import anomalies, public_statistics as stats, statistics_archive as archive
from _ftr_runtime import test_public_statistics as fixtures
from _ftr_runtime.mechanical_dictionary import LEGACY_CATEGORIES


class DictionaryV2Tests(unittest.TestCase):
    def test_confirmed_components(self):
        cases={
            'columna de dirección':'columna_direccion','caja de dirección':'caja_direccion','brazo Pittman':'brazo_pitman','rótulas de dirección':'rotulas_direccion','rótulas':'rotulas_direccion',
            'juego barra larga lado derecho':'barra_larga','barra corta izquierda':'barra_corta',
            'freno delantero':'frenos_delanteros','freno trasero':'frenos_traseros','flexible':'flexibles_freno',
            'flexible de freno':'flexibles_freno','tanque de aire':'tanque_aire','válvula de descarga':'valvula_descarga',
            'freno de servicio':'freno_servicio','freno de estacionamiento':'freno_estacionamiento','freno de emergencia':'freno_emergencia',
            'pulmón de freno delantero':'pulmon_freno','PF trasero derecho':'pulmon_freno',
            'amortiguador':'amortiguadores','buje de amortiguador':'bujes','bujes':'bujes','pulmón':'pulmon_suspension','pulmón de suspensión':'pulmon_suspension',
            'válvula niveladora':'valvula_niveladora','barra estabilizadora':'barra_estabilizadora','tensores delanteros':'tensores',
            'cardán':'cardan','juego de cruceta':'cruceta_direccion','neumático cortado':'neumatico_sin_ubicacion','cubierta pinchada':'neumatico_sin_ubicacion',
            'neumáticos delanteros':'neumaticos_delanteros','neumáticos traseros':'neumaticos_traseros','tuerca de rueda':'tuercas_rueda','bulones de rueda':'bulones_rueda',
            'corte de batería':'corte_corriente','cortacorriente':'corte_corriente','corte de corriente':'corte_corriente',
            'sonora marcha atrás':'sonora_marcha_atras','señal sonora de marcha atrás':'sonora_marcha_atras','alarma sonora de marcha atrás':'sonora_marcha_atras','chicharra no funciona':'sonora_marcha_atras','CHICHARRA':'sonora_marcha_atras'}
        for text,expected in cases.items():
            with self.subTest(text=text):
                known,unknown=anomalies.classify(text)
                self.assertEqual([r[1] for r in known],[expected]);self.assertEqual(unknown,[])

    def test_codes_individual_and_explicitly_confirmed_positions(self):
        for prefix,last in (('R',8),('A',6)):
            for n in range(1,last+1):
                with self.subTest(code=f'{prefix}{n}'):
                    known,unknown=anomalies.classify(f'{prefix}{n} flojo')
                    self.assertEqual(len(known),1);self.assertFalse(unknown)
                    expected='amortiguadores' if prefix=='A' else 'neumaticos_delanteros' if n<=2 else 'neumaticos_traseros'
                    self.assertEqual(known[0][1],expected)
                    if n<=2:self.assertEqual(known[0][2],'delantero izquierdo' if n==1 else 'delantero derecho')
                    else:
                        position='trasero'+(' izquierdo' if n%2 else ' derecho') if n<=6 else 'trasero'
                        if prefix=='R' and n<=6:position+=' interno' if n<=4 else ' externo'
                        self.assertEqual(known[0][2],position)
                        self.assertNotIn('interior',known[0][2]);self.assertNotIn('exterior',known[0][2])
        result=anomalies.analyze('R3 juego')['hallazgos'][0]
        self.assertEqual(result['referencia'],'r3');self.assertEqual(result['defecto'],'juego')

    def test_four_findings_with_and_without_punctuation(self):
        for text in ('R1 cortado, A2 flojo, PF trasero derecho y chicharra','R1 cortado A2 flojo PF trasero derecho chicharra','1. R1 cortado 2. A2 flojo 3. PF trasero derecho 4. chicharra','R1 cortado; A2 flojo\nPF trasero derecho y chicharra'):
            with self.subTest(text=text):
                known,unknown=anomalies.classify(text)
                self.assertEqual(len(known),4);self.assertFalse(unknown)
                self.assertEqual({r[0] for r in known},{'neumaticos','suspension','frenos','electrico'})

    def test_bushing_ownership_and_explicit_separate_defects(self):
        for text in ('A4 buje flojo','buje de amortiguador flojo','amortiguador con buje flojo','buje de A4 flojo'):
            with self.subTest(text=text):self.assertEqual([r[1] for r in anomalies.classify(text)[0]],['bujes'])
        self.assertEqual({r[1] for r in anomalies.classify('A4 roto y buje de A4 flojo')[0]},{'amortiguadores','bujes'})

    def test_duplicate_codes_locations_and_component_ownership(self):
        self.assertEqual(len(anomalies.classify('R1 cortado R1 cortado neumático delantero izquierdo cortado')[0]),1)
        self.assertEqual(len(anomalies.classify('R3 pinchado; R4 pinchado; R5 pinchado')[0]),3)
        known,_=anomalies.classify('barra larga derecha e izquierda; cardan y crucetas')
        self.assertEqual(len(known),3)  # Una barra, sin separar sus extremos.
        self.assertTrue(all(r[0]=='transmision' for r in known if r[1] in ('cardan','crucetas')))
        self.assertEqual([r[0] for r in anomalies.classify('PF y pulmón de suspensión')[0]],['frenos','suspension'])

    def test_undefined_ambiguous_negative_and_foreign_systems(self):
        for text in ('R9','R10','A9','A10','XR1','A12','R1ABC','PF123','chicharral','flexible de combustible','flexible de agua','pulmón de freno de suspensión','R1 trasero','R2 izquierdo','posible PF','R1 sin fallas','chicharra funciona bien','cubierta del motor','rótula de suspensión'):
            with self.subTest(text=text):
                known,unknown=anomalies.classify(text);self.assertFalse(known);self.assertTrue(unknown)
        known,unknown=anomalies.classify('R1 cortado y A9 DESCONOCIDO; CHICHARRA')
        self.assertEqual(len(known),2);self.assertEqual(unknown,['A9 DESCONOCIDO'])
        for text in ('no presenta falla de cardán y frenos','Frenos sin fallas ni cardán','quizá A1 y A2','sin novedad R1'):
            with self.subTest(text=text):self.assertFalse(anomalies.classify(text)[0])
        known,unknown=anomalies.classify('no presenta falla de cardán y frenos, R1 cortado')
        self.assertEqual([r[1] for r in known],['neumaticos_delanteros']);self.assertEqual(len(unknown),1)
        for text in ('sin chicharra','chicharra no anda','A1 está flojo'):
            with self.subTest(text=text):
                known,unknown=anomalies.classify(text);self.assertEqual(len(known),1);self.assertFalse(unknown)


class StatisticsV2PipelineTests(unittest.TestCase):
    setUp=fixtures.StatisticsPipelineTests.setUp
    tearDown=fixtures.StatisticsPipelineTests.tearDown
    sheet=fixtures.StatisticsPipelineTests.sheet
    google=fixtures.StatisticsPipelineTests.google
    visits=fixtures.StatisticsPipelineTests.visits
    read=fixtures.StatisticsPipelineTests.read

    def test_calendar_days_deduplicated_across_vehicles_and_lines(self):
        sheets=self.visits()
        sheets[0].cells[3,1]='01/01/2026';sheets[0].cells[5,1]='01/01/2026'
        self.google(sheets);data=self.read()
        self.assertEqual(data['mensual'][0]['controles'],3)
        self.assertEqual(data['mensual'][0]['dias_con_fiscalizaciones'],1)
        self.assertEqual(data['mensual'][1]['dias_con_fiscalizaciones'],1)
        self.assertTrue(all(m['dias_con_fiscalizaciones']==0 for m in data['mensual'][2:]))
        bad=copy.deepcopy(data);bad['mensual'][0]['dias_con_fiscalizaciones']=4
        with self.assertRaises(ValueError):stats.validate(bad)

    def test_formal_states_not_inferred_and_four_mentions_one_control(self):
        sheets=self.visits();sheets[0].cells[2,6]='R1 cortado, A2 flojo, PF trasero derecho y chicharra'
        self.google(sheets);data=self.read()
        self.assertEqual(data['totales']['registros_validos'],4)
        self.assertEqual(data['totales']['registros_fuera_de_servicio'],1)
        for category,component in (('neumaticos','neumaticos_delanteros'),('frenos','pulmon_freno'),('electrico','sonora_marcha_atras')):
            row=next(c for k in data['anomalias']['categorias'] if k['id']==category for c in k['componentes'] if c['id']==component)
            self.assertEqual(row['cantidad'],1);self.assertEqual(row['estados']['fuera_de_servicio'],1)

    def test_unknown_original_frequency_and_refs_only_in_cipher(self):
        sheets=self.visits();sheets[0].cells[2,6]='R1 cortado; ÑX_PRIVADO';sheets[0].cells[3,6]='ÑX_PRIVADO; A4 buje flojo'
        with patch.object(fixtures.admin,'seal',wraps=fixtures.admin.seal) as seal:self.google(sheets)
        private=seal.call_args.args[0]['novedades_sin_clasificar'];item=private['pendientes'][0]
        self.assertEqual(item['expresion'],'ÑX_PRIVADO');self.assertEqual(item['frecuencia'],2);self.assertEqual(item['estado'],'pendiente')
        self.assertEqual(item['periodo'],2026);self.assertEqual([r['fila'] for r in item['referencias']],[2,3])
        self.assertEqual(item['referencias'][0]['pestana'],'Línea 36/37')
        for name in archive.data_paths(self.root):
            text=(self.root/name).read_text(encoding='utf-8')
            for secret in ('ÑX_PRIVADO','novedades_original','pestana','fila','AA111AA','A4 buje'):self.assertNotIn(secret,text)

    def test_year_rollover_preserves_previous_bytes_and_different_lines(self):
        self.google(self.visits());before=(self.root/'estadisticas/2026.json').read_bytes()
        self.config['period']=2027;self.config['lines']=[dict(line=99,company=9999,enabled=True)]
        self.clock=datetime(2027,2,9,20,tzinfo=timezone.utc)
        self.google([self.sheet('LINEA 99',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],['05/02/2027','ZZ999ZZ',1,'OBSERVADO','R5 pinchado']])])
        self.assertEqual((self.root/'estadisticas/2026.json').read_bytes(),before)
        index=archive.validate_collection(self.root)
        self.assertEqual([r['periodo'] for r in index['periodos']],[2027,2026]);self.assertEqual(index['periodos'][0]['lineas'],[99]);self.assertEqual(index['periodos'][1]['lineas'],[36,37])
        self.assertEqual(self.read()['totales']['registros_validos'],1)
        old=json.loads(before)
        with self.assertRaisesRegex(ValueError,'revisión histórica'):stats.write(self.root,old)
        self.assertEqual((self.root/'estadisticas/2026.json').read_bytes(),before)

    def test_migration_keeps_legacy_counts_and_no_fake_days_or_components(self):
        self.google(self.visits());old=self.read();old['version']=1;old.pop('interpretacion');old.pop('calidad');old.pop('kit_sube')
        for month in old['mensual']:month.pop('dias_con_fiscalizaciones')
        old['anomalias']['version_reglas']=1
        old['anomalias'].pop('elementos_fisicos');old['anomalias'].pop('motor_revision')
        old['anomalias']['categorias']=[dict(id=k,cantidad=0,componentes=[dict(id=c,cantidad=0,estados={s:0 for s in stats.STATUS}) for c in components]) for k,components in LEGACY_CATEGORIES.items()]
        old['anomalias']['identificadas']=0;old['anomalias']['sin_clasificar']=0
        stats.validate(old)
        # Primera migración: solo existe el agregado V1, sin índice anual previo.
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=archive.encoded(old);(root/stats.FILE).write_bytes(original)
            newer=copy.deepcopy(self.read());newer['periodo']=2027;newer['lectura_planilla_utc']='2027-10-22T20:00:00+00:00';newer['corte_fecha']='2027-10-22'
            stats.write(root,newer)
            self.assertEqual((root/'estadisticas/2026.json').read_bytes(),original)
            restored=json.loads(original);self.assertNotIn('dias_con_fiscalizaciones',restored['mensual'][0]);self.assertEqual(restored['anomalias']['version_reglas'],1)
            archive.validate_collection(root)

    def test_failed_read_and_corruption_preserve_archive(self):
        self.google(self.visits());before={p:(self.root/p).read_bytes() for p in archive.data_paths(self.root)}
        sheets=self.visits();sheets[0].cells[2,3]='INVALIDO'
        with self.assertRaises(ValueError):self.google(sheets)
        self.assertEqual(before,{p:(self.root/p).read_bytes() for p in before})
        (self.root/'estadisticas/2026.json').write_bytes(before['estadisticas/2026.json']+b' ')
        with self.assertRaises(ValueError):archive.validate_collection(self.root)
        with self.assertRaises(ValueError):stats.write(self.root,self.read())

    def test_index_rejects_mixed_period_path_and_schema(self):
        self.google(self.visits());index=archive.validate_collection(self.root)
        self.assertEqual(len(index['periodos']),1)
        for mutate in (lambda r:r.update(archivo='../../privado.json'),lambda r:r.update(version=99),lambda r:r.update(version_reglas=99)):
            with self.subTest(mutate=mutate):
                bad=copy.deepcopy(index);mutate(bad['periodos'][0])
                with self.assertRaises(ValueError):archive.validate_index(bad)
        bad=copy.deepcopy(index);bad['periodos'][0]['lectura_planilla_utc']='2026-10-20T20:00:00+00:00'
        (self.root/stats.INDEX).write_bytes(archive.encoded(bad))
        with self.assertRaises(ValueError):archive.validate_collection(self.root)
