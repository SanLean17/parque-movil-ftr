"""Regression and annual rollover checks using isolated, fictitious records."""
import copy
import json
from datetime import datetime, timezone
import pytest
from _ftr_runtime import anomalies, dictionary_rules as rules, kit_sube
from _ftr_runtime.test_source_pipeline import SourcePipelineTests


@pytest.mark.parametrize('text', ['NO COINCIDE: KIT','KIT: INCORRECTO','KIT - NO COINCIDE',
    'NO-COINCIDE-KIT','NO  COINCIDE : KIT','KIT, MAL','KIT SUBE: NO COINCIDE','KIT: MAL, KIT'])
def test_kit_punctuation_is_not_mechanical(text):
    event=dict(linea=36,tiene_novedades=True,novedades=text,estado='SIN NOVEDAD')
    before=copy.deepcopy(event)
    assert anomalies.analyze(text)['pendientes']==[]
    assert anomalies.analyze(text)['hallazgos']==[]
    assert kit_sube.aggregate([event],[dict(linea=36,registros_periodo=1)])['controles_con_incidencia']==1
    assert event==before


@pytest.mark.parametrize('text', ['KIT: INCORRECTO; PF1 Y AMORTIGUADOR 3 - falla zzz',
    'PF1, NO COINCIDE: KIT; AMORTIGUADOR 3 - falla zzz'])
def test_kit_preserves_real_findings_and_unknowns(text):
    result=anomalies.analyze(text)
    assert {f['componente'] for f in result['hallazgos']}=={'pulmon_freno','amortiguadores'}
    assert result['pendientes']==['falla zzz']


@pytest.mark.parametrize('text', ['NO COINCIDE; KIT','NO COINCIDE\nKIT','KIT; INCORRECTO'])
def test_kit_does_not_consume_other_anomaly(text):
    assert anomalies.analyze(text)['pendientes']


def test_kit_does_not_take_condition_from_next_component():
    for text in ('KIT - NO FUNCIONA CHICHARRA','KIT; NO FUNCIONA CHICHARRA'):
        result=anomalies.analyze(text)
        assert result['hallazgos'][0]['componente']=='sonora_marcha_atras'
        assert result['hallazgos'][0]['defecto']=='no_funciona'


@pytest.mark.parametrize('text', ['TENSOR  SUB','TENSOR\tSUB','tensor   sub'])
def test_tensor_spacing(text):
    result=anomalies.analyze(text)
    assert not result['pendientes']
    assert result['hallazgos'][0]['ubicacion']=='superior'


def test_spelling_same_validation_preview_and_application():
    rule=dict(tipo='ortografia',expresion='tensor subb',corregida='tensor sub',habilitada=True)
    dictionary=rules.validate(dict(rules.EMPTY,reglas=[rule]))
    compiled=rules.compile_rules(json.loads(rules.encoded(dictionary)))
    for text in ('tensor subb','tensor  subb'):
        result=anomalies.analyze(text,compiled)
        assert result['hallazgos']==anomalies.analyze(rule['corregida'])['hallazgos']
        assert result['pendientes']==[]
    # Context cannot cross an anomaly boundary or manufacture a component.
    for text in ('AMORTIGUAR','BUJE DE; AMORTIGUAR','TENSOR; SUB'):
        assert anomalies.analyze(text)['pendientes']
    result=anomalies.analyze('BUJE DE  AMORTIGUAR; falla zzz')
    assert result['hallazgos'][0]['componente']=='bujes'
    assert result['pendientes']==['falla zzz']


def test_engine9_capsule_remains_verifiable():
    from _ftr_runtime import mechanical_review as review, legacy_mechanics_v9
    from _ftr_runtime.public_statistics import FILE
    test=SourcePipelineTests();test.setUp()
    try:
        rows=[['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
              ['01/10/2026',36,'AA111AA',1,'OBSERVADO','NO COINCIDE: KIT; TENSOR  SUB']]
        test.google([test.sheet('LINEA 36/37',rows)])
        data=json.loads((test.root/FILE).read_bytes())
        from datetime import date
        events=[dict(linea=36,fecha=date(2026,10,1),dominio='AA111AA',interno=1,estado='OBSERVADO',
            estado_original='OBSERVADO',tiene_novedades=True,novedades=rows[1][-1],pestana='LINEA 36/37',pestana_posicion=1,fila=2)]
        data['anomalias']=legacy_mechanics_v9.mechanics(events,dictionary=rules.EMPTY)[0]
        capsule=review.snapshot(events,data,rules.EMPTY);capsule['motor_revision']=9
        assert review.unpack(capsule)[1]==data
        result=review.preview(capsule,rules.EMPTY)
        assert result['antes']['sin_clasificar']==2 and result['despues']['sin_clasificar']==0
        assert result['afectados'] and result['motor_despues']==10
    finally:test.tearDown()


def test_rollover_2027_2028_2029_preserves_history_fleet_and_schedule():
    test=SourcePipelineTests();test.setUp()
    try:
        header=['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES']
        test.google([test.sheet('LINEA 36/37',[header,['01/10/2026',36,'AA111AA',1,'OBSERVADO','BARTA CORTA PITMAN']])])
        archived={2026:(test.root/'estadisticas/2026.json').read_bytes()}
        fleet={p.name:p.read_bytes() for p in (test.root/'parques').glob('*.csv')}
        settings=copy.deepcopy(test.config)
        for year in (2027,2028,2029):
            test.config['period']=year
            test.config['sheetUrl']=f'https://docs.google.com/spreadsheets/d/FICTITIOUS_ANNUAL_{year}_SOURCE/edit'
            test.clock=datetime(year,2,1,20,tzinfo=timezone.utc)
            test.google([test.sheet('LINEA 36/37',[header])])
            fresh=json.loads((test.root/f'estadisticas/{year}.json').read_bytes())
            assert fresh['totales']['registros_validos']==0
            assert fresh['kit_sube']['controles_con_incidencia']==0
            for past,raw in archived.items():assert (test.root/f'estadisticas/{past}.json').read_bytes()==raw
            assert fleet=={p.name:p.read_bytes() for p in (test.root/'parques').glob('*.csv')}
            test.google([test.sheet('LINEA 36/37',[header,[f'01/01/{year}',36,'AA111AA',1,'OBSERVADO','BARTA CORTA PITMAN; NO COINCIDE: KIT']])])
            populated=json.loads((test.root/f'estadisticas/{year}.json').read_bytes())
            assert populated['totales']['registros_validos']==1
            assert populated['anomalias']['identificadas']==1 and populated['anomalias']['sin_clasificar']==0
            assert populated['kit_sube']['controles_con_incidencia']==1
            archived[year]=(test.root/f'estadisticas/{year}.json').read_bytes()
        assert {k:v for k,v in test.config.items() if k not in ('period','sheetUrl')}=={k:v for k,v in settings.items() if k not in ('period','sheetUrl')}
    finally:test.tearDown()
