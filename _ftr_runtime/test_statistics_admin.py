import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from _ftr_runtime import dictionary_rules as rules, anomalies, historical_statistics as history, statistics_archive as archive, public_statistics as stats
from _ftr_runtime import test_source_pipeline as fixtures
from _ftr_runtime.statistics_commands import clean

class DictionaryTests(unittest.TestCase):
    def rule(self,**kw):return dict(expresion='X12',categoria='direccion',componente='barra_larga',habilitada=True,**kw)
    def test_confirm_modify_disable_and_persistence(self):
        d=rules.proposed(rules.EMPTY,[self.rule()],rules.digest(rules.EMPTY))
        self.assertEqual(d['revision'],2)
        custom=rules.compile_rules(json.loads(rules.encoded(d)))
        a=anomalies.analyze('X12 flojo; X12 flojo; PF roto',custom)
        self.assertEqual({f['componente'] for f in a['hallazgos']},{'barra_larga','pulmon_freno'})
        self.assertEqual(len(a['hallazgos']),2);self.assertFalse(a['pendientes'])
        row=dict(d['reglas'][0],componente='barra_corta')
        d=rules.proposed(d,[row],rules.digest(d))
        self.assertEqual(anomalies.analyze('X12',rules.compile_rules(d))['hallazgos'][0]['componente'],'barra_corta')
        d['reglas'][0]['habilitada']=False
        self.assertEqual(anomalies.analyze('X12',rules.compile_rules(d))['pendientes'],['X12'])
    def test_validation_and_conflicts(self):
        for expression in ('','roto','sin','R1','R9','PF','cardán','AA123BB','ABC123','Línea 91','texto del inspector','x.*','__import__','x;rm','x\nsecret'):
            with self.subTest(expression=expression),self.assertRaises(ValueError):rules.validate(dict(version=1,revision=1,reglas=[dict(self.rule(),expresion=expression)]))
        with self.assertRaises(ValueError):rules.proposed(rules.EMPTY,[self.rule()], '0'*64)
        with self.assertRaises(ValueError):rules.validate(dict(version=1,revision=1,reglas=[self.rule(),dict(self.rule(),componente='barra_corta')]))
        with self.assertRaises(ValueError):rules.validate(dict(version=1,revision=1,reglas=[dict(self.rule(),categoria='frenos')]))
    def test_negation_and_word_boundaries_remain_conservative(self):
        d=rules.proposed(rules.EMPTY,[self.rule()],rules.digest(rules.EMPTY));custom=rules.compile_rules(d)
        for text in ('X123','AX12','no presenta falla de X12','posible X12'):
            with self.subTest(text=text):self.assertFalse(anomalies.analyze(text,custom)['hallazgos'])

class HistoricalTests(unittest.TestCase):
    setUp=fixtures.SourcePipelineTests.setUp
    tearDown=fixtures.SourcePipelineTests.tearDown
    sheet=fixtures.SourcePipelineTests.sheet
    sheets=fixtures.SourcePipelineTests.sheets
    google=fixtures.SourcePipelineTests.google
    def historical(self,rows=None):
        return [self.sheet('Línea 999',rows or [['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],['01/02/2025','AA111AA',7,'FUERA DE SERVICIO','PF, barra larga'],['01/02/2025','AA111AA',7,'OBSERVADO','X12']])]
    def build(self,sheets,**kw):return history.build(sheets,2025,'HISTORICAL_SOURCE_1234567','2026-10-22T22:00:00+00:00',rules.EMPTY,**kw)
    def test_independent_year_and_future_empty_preserve_archives(self):
        self.google(self.sheets());before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        data,report,detail=self.build(self.historical())
        self.assertEqual(data['totales']['registros_validos'],2);self.assertEqual(data['mensual'][1]['dias_con_fiscalizaciones'],1)
        self.assertEqual(data['anomalias']['identificadas'],2);self.assertEqual(data['anomalias']['sin_clasificar'],1)
        self.assertEqual([r['linea'] for r in data['lineas']],[999])
        history.add_archive(self.root,data)
        for p,b in before.items():
            if p.name!='indice.json':self.assertEqual(p.read_bytes(),b,p)
        old=(self.root/'estadisticas/2025.json').read_bytes();active=(self.root/'estadisticas/2026.json').read_bytes()
        with self.assertRaises(ValueError):history.add_archive(self.root,data)
        empty=copy.deepcopy(data);empty.update(periodo=2027,lectura_planilla_utc='2027-01-01T20:00:00+00:00',corte_fecha='2027-01-01')
        empty['totales']={k:0 for k in stats.TOTALS};empty['lineas']=[{k:(999 if k=='linea' else 0) for k in stats.LINE_FIELDS}]
        from datetime import date
        empty['mensual']=stats.monthly([],2027,date(2027,1,1));empty['proporciones']=stats.proportions(empty['lineas']);empty['destacados']=stats.ranking(empty['lineas']);empty['anomalias']=stats.mechanics([])[0]
        archive.publish(self.root,empty)
        self.assertEqual((self.root/'estadisticas/2025.json').read_bytes(),old);self.assertEqual((self.root/'estadisticas/2026.json').read_bytes(),active)
        self.assertEqual([r['periodo'] for r in archive.validate_collection(self.root)['periodos']],[2027,2026,2025])
    def test_partial_requires_explicit_authorization_and_never_invents_year(self):
        sheets=self.historical();sheets[0].cells[3,1]='01/02/225'
        with self.assertRaises(ValueError):self.build(sheets)
        data,report,detail=self.build(sheets,allow_partial=True)
        self.assertTrue(data['calidad']['parcial']);self.assertEqual(data['totales']['registros_validos'],1)
        for e in ('novedades_original','pestana','AA111AA','X12'):self.assertNotIn(e,json.dumps(data))
        sheets[0].cells[2,1]='01/01/2026'
        with self.assertRaises(ValueError):self.build(sheets,allow_partial=True)
    def test_missing_state_warning_has_exact_cell_and_stays_valid(self):
        sheets=[self.sheet('Línea 36',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],['01/01/2026','AA111AA',1,'','PF']]),self.sheet('Línea 37',[['FECHA','DOMINIO','INTERNO','NOVEDADES'],['02/01/2026','AB222CD',2,'PF']])]
        with patch.object(fixtures.admin,'seal',wraps=fixtures.admin.seal) as seal:self.google(sheets)
        details=seal.call_args.args[0]
        missing=next(x for x in details['incidencias'] if x['codigo']=='CONTROL_SIN_ESTADO')
        self.assertEqual((missing['celda'],missing['columna'],missing['fila'],missing['pestana_posicion']),('D2','D',2,1))
        no_column=next(x for x in details['incidencias'] if x['codigo']=='COLUMNA_ESTADO_AUSENTE')
        self.assertIsNone(no_column['celda']);self.assertEqual(no_column['categoria'],'advertencia')
        self.assertEqual(json.loads((self.root/stats.FILE).read_bytes())['totales']['registros_sin_estado'],2)
    def test_wrong_year_cannot_become_valid_empty_source(self):
        with self.assertRaises(ValueError):self.google(self.historical())

    def test_import_changes_only_annual_index_manifest_and_downloads_once(self):
        from _ftr_tools.statistics_admin import apply
        from _ftr_runtime.config import digest
        self.google(self.sheets())
        (self.root/'_ftr_config.json').write_text(json.dumps(self.config))
        (self.root/'ftr_publicacion.json').write_text(json.dumps({'period':2026,'files_sha256':{}}))
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        command=dict(period=2025,sheetUrl='HISTORICAL_SOURCE_1234567',allow_partial=False)
        from unittest.mock import Mock
        export=Mock(return_value=b'FICTICIO')
        with patch.object(fixtures.admin.base,'decode_xlsx',return_value=self.historical()):
            paths=apply(self.root,'history-import',command,digest(self.config),export=export)
        self.assertEqual(set(paths),{'estadisticas/2025.json',stats.INDEX,'ftr_publicacion.json'})
        export.assert_called_once_with('HISTORICAL_SOURCE_1234567')
        for p,body in before.items():
            if p.relative_to(self.root).as_posix() not in paths:self.assertEqual(p.read_bytes(),body,p)
        archive.validate_collection(self.root)
        with self.assertRaises(ValueError):apply(self.root,'history-import',command,digest(self.config),export=export)
        export.assert_called_once()

    def test_dictionary_save_never_reads_sources_or_rewrites_statistics(self):
        from _ftr_tools.statistics_admin import apply
        from _ftr_runtime.config import digest
        from unittest.mock import Mock
        self.google(self.sheets())
        (self.root/'_ftr_config.json').write_text(json.dumps(self.config))
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        export=Mock(side_effect=AssertionError('No se lee ninguna fuente'))
        payload=dict(expected_dictionary=rules.digest(rules.EMPTY),reglas=[DictionaryTests().rule()])
        self.assertEqual(apply(self.root,'dictionary-save',payload,digest(self.config),export=export),[rules.FILE])
        for p,body in before.items():self.assertEqual(p.read_bytes(),body,p)
        with self.assertRaises(ValueError):apply(self.root,'dictionary-save',payload,digest(self.config),export=export)
        export.assert_not_called()

    def test_state_header_in_separate_auxiliary_table_is_not_attached(self):
        sheet=self.sheet('Línea 36',[['FECHA','DOMINIO','INTERNO','','ESTADO'],['01/01/2026','AA111AA',1,'','FUERA DE SERVICIO']])
        event=next(fixtures.admin.source_rows([sheet],include_novedades=True))
        self.assertFalse(event['tiene_estado']);self.assertEqual(event['estado'],'')

if __name__=='__main__':unittest.main()
