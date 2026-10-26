"""Confirmed FTR vocabulary; synthetic records, no source or publication I/O."""
import copy
from collections import Counter
from datetime import date
import pytest
from _ftr_runtime import anomalies, dictionary_rules as rules, mechanical_review, public_statistics
from _ftr_runtime.technical_fields import validate_extra

# Component, location, defect, quantity, part, subcomponent, reference.
def f(component, location='sin_ubicacion', defect='no_identificado', quantity=None, part=None, sub=None, ref=None):
    return (component,location,defect,quantity,part,sub,ref)

CASES={
 'BUJES TRASEROS DE AMORTIGUADORES, AMBOS.':[f('bujes','trasero',quantity=2)],
 'FALTA BARRA ESTABILIZADORA Y AMORTIGUADOR DE DIRECCIÓN, AMBOS.':[f('barra_estabilizadora',defect='faltante',quantity=1),f('amortiguador_direccion',quantity=2)],
 'AMORTIGUADORES AMBOS DELANTEROS CON JUEGO':[f('amortiguadores','delantero','juego',2)],
 'AMORTIGUADOR TRASERO IZQUIERDO ÚLTIMO CON JUEGO':[f('amortiguadores','trasero izquierdo','juego')],
 'TENSOR DELANTERO IZQUIERDO AMBOS MOÑOS':[f('tensores','delantero izquierdo',quantity=1,part='ambos moños')],
 'AMBOS TENSORES SUPERIORES DELANTEROS IZQUIERDO Y DERECHO MOÑO TRASERO':[f('tensores','delantero izquierdo superior',quantity=1,part='moño trasero'),f('tensores','delantero derecho superior',quantity=1,part='moño trasero')],
 'TENSOR IZQUIERDO MOÑO TRASERO NO TIENE BUJE':[f('tensores','izquierdo','faltante',part='moño trasero',sub='buje')],
 'MANGUERA DE FRENO':[f('flexibles_freno')], 'MANGUERA DE FRENOS':[f('flexibles_freno')],
 'FLEXIBLE DEL PULMÓN DE FRENO':[f('flexibles_freno')], 'FRENOS':[f('freno_sin_ubicacion')],
 'BARRA LARGA EXT IZQUIERDO':[f('barra_larga','izquierdo',part='extremo')],
 'LARGA A4 SUELTO':[f('barra_larga'),f('amortiguadores','trasero derecho','suelto',ref='a4')],
 'TENSOR TRAS ISK':[f('tensores','trasero izquierdo')],
 'A5, A4 SUELTOS TENSOR DEL IZQUIERDO MOÑO TRA':[f('amortiguadores','trasero izquierdo','suelto',1,ref='a5'),f('amortiguadores','trasero derecho','suelto',1,ref='a4'),f('tensores','delantero izquierdo',part='moño trasero')],
 'FALTANTE DE BULÓN R6':[f('bulones_rueda','trasero derecho externo','faltante',ref='r6')],
 'AMORTIGUADOR TRASERO IZQUIERDO SUELTO Y R3, R5 CORTADAS':[f('amortiguadores','trasero izquierdo','suelto'),f('neumaticos_traseros','trasero izquierdo interno','corte',1,ref='r3'),f('neumaticos_traseros','trasero izquierdo externo','corte',1,ref='r5')],
 'PULMÓN DE FRENO TRASERO IZQUIERDO PINCHADO Y NEUMÁTICO TRASERO IZQUIERDO INTERNO CORTAD':[f('pulmon_freno','trasero izquierdo','pinchadura'),f('neumaticos_traseros','trasero izquierdo interno','corte')],
 'CHICHARRA MARCHA ATRÁS':[f('sonora_marcha_atras')],
 'REGULAR FRENO DE EMERGENCIA':[f('freno_emergencia',defect='ajuste')],
 'CARECE DE AMORTIGUACIÓN DE DIRECCIÓN DERECHO':[f('amortiguador_direccion','derecho','faltante')],
 'PÉRDIDA DE AIRE ZONA CENTRAL':[f('perdida_aire_no_especificada','zona central','perdida_aire')],
 'PÉRDIDA DE AIRE ZONA DELANTERA':[f('perdida_aire_no_especificada','delantero','perdida_aire')],
 'PÉRDIDA DE AIRE ZONA MEDIA':[f('perdida_aire_no_especificada','zona media','perdida_aire')],
 'PÉRDIDA DE AIRE POR PUERTA':[f('perdida_aire_no_especificada',defect='perdida_aire')],
 'PÉRDIDA DE AIRE POR PEDALERA':[f('perdida_aire_no_especificada',defect='perdida_aire')],
 'PÉRDIDA DE AIRE POR GOBERNADORA':[f('perdida_aire_no_especificada',defect='perdida_aire')],
 'PÉRDIDA POR CODO EN PULMÓN DE FRENO TRASERO DERECHO':[f('pulmon_freno','trasero derecho','perdida',sub='codo')],
 'PÉRDIDA POR VIGÍA':[f('perdida_no_especificada',defect='perdida')],
 'PÉRDIDA DE FLUIDOS POR CAJA':[f('transmision_sin_componente',defect='perdida_fluidos')],
 'PÉRDIDA EN ZONA TRASERA':[f('perdida_no_especificada','trasero','perdida')],
 'LEAK HIDRÁULICO':[f('perdida_hidraulica',defect='perdida')],
 'CON TABLERO NUEVO':[f('observacion_administrativa')],
 'BUJE TRASERO PARTE IZQUIERDA TORCIDA REPARADA':[f('bujes','trasero izquierdo','torcido')],
}
for text in ('PS6','PS.6','PS-6','PS_6','PS 6','P S 6','PULMÓN DE SUSPENSIÓN 6'):
    CASES[text]=[f('pulmon_suspension','trasero derecho ultimo',ref='ps6')]
CASES.update({
 'PÉRDIDA LEVE AIRE ZONA MEDIA':[f('perdida_aire_no_especificada','zona media','perdida_aire')],
 'LARGA, A4 SUELTO':CASES['LARGA A4 SUELTO'],
 'CHICHARRA MARCHAS ATRÁS':CASES['CHICHARRA MARCHA ATRÁS'],
 'BUJE DE AMORTIGUADOR 2':[f('bujes','delantero derecho',ref='a2')],
 'AMORTIGUADORES AMBOS DELANTEROS CON JUEGO Y AMORTIGUADOR TRASERO IZQUIERDO ÚLTIMO. CON JUEGO.':[f('amortiguadores','delantero','juego',2),f('amortiguadores','trasero izquierdo','juego')],
 'AMORTIGUADOR TRASERO IZQUIERDO SUELTO Y R3_R5 CORTADAS':CASES['AMORTIGUADOR TRASERO IZQUIERDO SUELTO Y R3, R5 CORTADAS'],
})

def assert_result(result,expected):
    fields=('componente','ubicacion','defecto','cantidad_fisica','parte','subcomponente','referencia')
    assert Counter(tuple(row[k] for k in fields) for row in result['hallazgos'])==Counter(expected)
    assert not result['pendientes']
    for row in result['hallazgos']:
        assert row['componente'] in anomalies.CATEGORIES[row['categoria']]
        validate_extra(row)

@pytest.mark.parametrize('text,expected',CASES.items())
def test_confirmed_full_observations(text,expected):
    assert_result(anomalies.analyze(text),expected)

@pytest.mark.parametrize('text', ['PS5','PS7','PS60','MANGUERA DE VÁLVULA CUATRO VÍAS','CARECE DE AMORTIGUACIÓN','EXT','AMBOS','*-'])
def test_unknown_is_never_hidden(text):
    result=anomalies.analyze(text)
    assert not result['hallazgos'] and result['pendientes']==[text]

def test_partial_scope_and_deterministic_ambiguity():
    result=anomalies.analyze('TENSOR IZQUIERDO MOÑO DEL FRENO EMER')
    assert len(result['hallazgos'])==1 and result['hallazgos'][0]['parte']=='moño'
    assert result['pendientes']==['FRENO EMER']
    result=anomalies.analyze('TENSOR IZQUIERDO MOÑO DEL. FRENO EMER')
    assert len(result['hallazgos'])==1 and result['hallazgos'][0]['parte']=='moño'
    assert result['pendientes']==['FRENO EMER']
    result=anomalies.analyze('BARRA LARGA EXTREMO IZQUIERDO Y FLEXIBLE DE PUNTO FRENO DEL ACERO IZQUIERDO')
    assert Counter(f['componente'] for f in result['hallazgos'])=={'barra_larga':1,'flexibles_freno':1}
    assert result['pendientes']==['ACERO IZQUIERDO']
    assert next(f for f in result['hallazgos'] if f['componente']=='flexibles_freno')['ubicacion']=='sin_ubicacion'
    assert anomalies.analyze('PS6 Y PF6')['hallazgos'][0]['componente']=='pulmon_freno'
    assert len(anomalies.analyze('PS6 Y PF6')['hallazgos'])==2
    assert anomalies.analyze('BARRA LARGA; *-')['pendientes']==['*-']

@pytest.mark.parametrize('text', ['PÉRDIDA DE AIRE EN PULMÓN DE FRENO','PULMÓN DE FRENO CON PÉRDIDA DE AIRE'])
def test_air_loss_belongs_to_explicit_component(text):
    result=anomalies.analyze(text)
    assert_result(result,[f('pulmon_freno',defect='perdida_aire')])

@pytest.mark.parametrize('year',[2025,2026,2027,2028])
def test_global_rules_preserve_original_controls_states_and_unknowns(year):
    texts=[*CASES,'MANGUERA DE VÁLVULA CUATRO VÍAS','*-']
    events=[dict(fecha=date(year,1,1),linea=999,estado='SIN NOVEDAD',estado_original='SIN NOVEDAD',novedades=t,tiene_novedades=True) for t in texts]
    before=copy.deepcopy(events)
    data,private=public_statistics.mechanics(events,dictionary=rules.EMPTY)
    assert events==before and data['cobertura']['registros_validos']==len(events)
    assert data['sin_clasificar']==2 and sum(r['frecuencia'] for r in private['pendientes'])==2
    assert data['identificadas']==sum(len(CASES[t]) for t in CASES)
    for category in data['categorias']:
        for c in category['componentes']:assert c['estados']['sin_novedad']==c['cantidad']
    others=next(c for c in data['categorias'] if c['id']=='otras')
    assert others['cantidad']>data['sin_clasificar']

def test_engine10_capsule_replay_and_full_preview():
    from _ftr_runtime import legacy_mechanics_v10
    from _ftr_runtime.test_source_pipeline import SourcePipelineTests
    test=SourcePipelineTests();test.setUp()
    try:
        text='PS6; PÉRDIDA DE AIRE POR PUERTA; BUJES TRASEROS DE AMORTIGUADORES, AMBOS.'
        test.google([test.sheet('LINEA 36/37',[['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],['01/10/2026',36,'AA111AA',1,'OBSERVADO',text]])])
        import json
        data=json.loads((test.root/public_statistics.FILE).read_bytes())
        events=[dict(fecha=date(2026,10,1),linea=36,dominio='AA111AA',interno=1,estado='OBSERVADO',tiene_novedades=True,novedades=text)]
        data['anomalias']=legacy_mechanics_v10.mechanics(events,dictionary=rules.EMPTY)[0]
        capsule=mechanical_review.snapshot(events,data,rules.EMPTY);capsule['motor_revision']=10
        frozen=copy.deepcopy(capsule)
        assert mechanical_review.unpack(capsule)[1]==data
        preview=mechanical_review.preview(capsule,rules.EMPTY)
        assert preview['antes']['sin_clasificar']>0 and preview['despues']['sin_clasificar']==0
        assert preview['motor_despues']==11 and preview['afectados']
        assert capsule==frozen
    finally:test.tearDown()
