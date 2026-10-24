"""Casos confirmados FTR, KIT y ortografía con datos exclusivamente ficticios."""
from collections import Counter
from datetime import date
import copy
import pytest
from _ftr_runtime.anomalies import analyze
from _ftr_runtime import dictionary_rules as rules,kit_sube

CASES={
 'BARTA CORTA PITMAN':{'barra_corta':1},'CORTA PITMAN':{'barra_corta':1},
 'BARRA CORTA LADO PITMAN':{'barra_corta':1},'BARRA CORTA LADO EJE':{'barra_corta':1},
 'BARRA CORTA COMPLETA':{'barra_corta':1},'BARRA CORTA ENTERA':{'barra_corta':1},
 'BARRA CORTA AMBOS EXTREMOS CON JUEGO Y CRUCETA 3 CON JUEGO':{'barra_corta':1,'cruceta_direccion':1},
 'LARGA DERECHA':{'barra_larga':1},'LARGA DERECHO':{'barra_larga':1},'BARRA LARGA LADO IZQUIERDO':{'barra_larga':1},
 'AMOR DIRECCIÓN':{'amortiguador_direccion':1},'CRUCETA':{'cruceta_direccion':1},'CR1':{'cruceta_direccion':1},'CR2':{'cruceta_direccion':1},'CR3':{'cruceta_direccion':1},'CARDÁN CR2':{'cruceta_direccion':1},'CRUCETA 3 CON JUEGO':{'cruceta_direccion':1},'CRUCETA DE TRANSMISIÓN':{'crucetas':1},
 'TENSOR SUP E INF MOÑO TRAS':{'tensores':2},'TENSOR DER MONIO DEL':{'tensores':1},'TENSOR ISK':{'tensores':1},'TENSOR SUB':{'tensores':1},
 'AMORTIGUADOR 3':{'amortiguadores':1},'A3':{'amortiguadores':1},'A5 Y 6 SUELTOS':{'amortiguadores':2},'A5-A6':{'amortiguadores':2},
 'AMORTIGUADOR 3,5Y4 Y PF4':{'amortiguadores':3,'pulmon_freno':1},
 'AMORTIGUADOR DELANTERO DERECHO GIRA':{'amortiguadores':1},'A2 FLOJO':{'amortiguadores':1},'A4 SULETO':{'amortiguadores':1},
 'BUGE AMORTIGUADOR':{'bujes':1},'BUJE DE AMORTIGUAR':{'bujes':1},
 'AMORTIGUADORES AMBOS DELANTEROS CON JUEGO':{'amortiguadores':1},'AMORTIGUADOR TRASERO IZQUIERDO ÚLTIMO, CON JUEGO':{'amortiguadores':1},
 'PS1':{'pulmon_suspension':1},'PS.1':{'pulmon_suspension':1},'PS 1':{'pulmon_suspension':1},
 'PF1':{'pulmon_freno':1},'PF.1':{'pulmon_freno':1},'PF-1':{'pulmon_freno':1},'PF 1':{'pulmon_freno':1},
 'PULMÓN DE FRENO 1 Y 4':{'pulmon_freno':2},'PULMÓN DE FRENO 1 PINCHADO':{'pulmon_freno':1},
 'PULMÓN DE FRENO TRASERO IZQUIERDO DIAFRAGMA':{'pulmon_freno':1},'FLEXIBLE PULMÓN DE FRENO DELANTERO IZQUIERDO':{'flexibles_freno':1},
 'BLOQUEO':{'bloqueo_frenos':1},'BLOQUEO NO FUNCIONA':{'bloqueo_frenos':1},'SISTEMA DE FRENO':{'freno_sin_ubicacion':1},'SISTEMA FRENO TRASERA':{'freno_sin_ubicacion':1},
 'R3 LISA':{'neumaticos_traseros':1},'R4 CORTADO':{'neumaticos_traseros':1},'AMBOS NEUMÁTICOS TRASEROS INTERNOS CORTADOS':{'neumaticos_traseros':1},
 'CHICHARRA':{'sonora_marcha_atras':1},'SEÑAL SONORA':{'sonora_marcha_atras':1},'SEÑAL ACÚSTICA':{'sonora_marcha_atras':1},'SONORA MARCHA ATRÁS':{'sonora_marcha_atras':1},'CHICHARRA NO FUNCIONA':{'sonora_marcha_atras':1},
 'CARECE DE AMORTIGUADOR':{'amortiguadores':1},'PÉRDIDA DE FLUIDOS POR DIFERENCIAL':{'diferencial':1},
 'PF1 Y AMORTIGUADOR 3':{'pulmon_freno':1,'amortiguadores':1},'CARDAN CR2, BARRA CORTA DELANTERO':{'cruceta_direccion':1,'barra_corta':1},
 'BARRA ESTABILIZADORA Y AMORTIGUADOR DE DIRECCIÓN, CHICHARRA':{'barra_estabilizadora':1,'amortiguador_direccion':1,'sonora_marcha_atras':1},
 'EXTREMO BARRA LARGA':{'barra_larga':1},'EXTREMO BARRA CORTA':{'barra_corta':1},'TENSOR EXTREMO DERECHO':{'tensores':1},'EXTREMOS BARRA LARGA - CRUCETA 2':{'barra_larga':1,'cruceta_direccion':1},'EXTREMO DELANTERO DE BARRA CORTA':{'barra_corta':1},'BARRA LARGA, EXTREMO IZQUIERDO CON JUEGO':{'barra_larga':1},
}

@pytest.mark.parametrize('text,expected',CASES.items())
def test_confirmed(text,expected):
    result=analyze(text)
    assert Counter(f['componente'] for f in result['hallazgos'])==expected
    assert not result['pendientes']

def test_details_and_ambiguity():
    for text in ('EXTREMO','AMBOS EXTREMOS','CARECE DE AMORTIGUACIÓN','SUPERIOR','ZONA CENTRAL'):
        r=analyze(text);assert not r['hallazgos'] and r['pendientes']
    for text in ('AMORTIGUADORES AMBOS DELANTEROS CON JUEGO','AMBOS NEUMÁTICOS TRASEROS INTERNOS CORTADOS'):
        assert analyze(text)['hallazgos'][0]['cantidad_fisica']==2
    assert analyze('BARRA CORTA COMPLETA')['hallazgos'][0]['parte']=='ambos extremos'
    assert analyze('PULMÓN DE FRENO 1 PINCHADO')['hallazgos'][0]['subcomponente'] is None
    assert analyze('PULMÓN DE FRENO TRASERO IZQUIERDO DIAFRAGMA')['hallazgos'][0]['subcomponente']=='diafragma'
    assert analyze('AMORTIGUADOR DELANTERO DERECHO GIRA')['hallazgos'][0]['defecto']=='flojo'
    for n in (7,8):assert analyze('R'+str(n))['hallazgos'][0]['ubicacion']=='trasero'

@pytest.mark.parametrize('text',['KIT','NO COINCIDE KIT','KIT NO COINCIDE','KIT INCORRECTO','KIT MAL','NO KIT','kit. KIT; kit','KIT_SUBE','KIT SUBE NO FUNCIONA','NO TIENE KIT','KIT ROTO'])
def test_kit_independent(text):
    e=dict(linea=1,tiene_novedades=True,novedades=text,estado='SIN NOVEDAD',kit_desmontaje='123')
    assert kit_sube.aggregate([e],[dict(linea=1,registros_periodo=1)])['controles_con_incidencia']==1
    assert analyze(text)['hallazgos']==[] and analyze(text)['pendientes']==[]
    assert e['estado']=='SIN NOVEDAD'

def test_kit_not_substring_or_other_column_and_unknown_retained():
    for text in ('skittle','kitten','sin novedad',''):
        assert not kit_sube.detected(dict(tiene_novedades=True,novedades=text,kit_desmontaje='123'))
    r=analyze('KIT INCORRECTO, PF1 Y AMORTIGUADOR 3 - falla zzz')
    assert len(r['hallazgos'])==2 and r['pendientes']==['falla zzz']
    rows=[dict(linea=1,registros_periodo=0)]
    assert kit_sube.aggregate([],rows)['controles_con_incidencia']==0
    assert kit_sube.aggregate([],rows,True)['controles_con_incidencia'] is None

def test_new_spelling_literal_context_and_conflicts():
    rule=dict(tipo='ortografia',expresion='amortiguadr',corregida='amortiguador',habilitada=True)
    dictionary=rules.validate(dict(rules.EMPTY,reglas=[rule]));compiled=rules.compile_rules(dictionary)
    text='AMORTIGUADR 3 FLOJO, PF1'
    assert len(analyze(text,compiled)['hallazgos'])==2 and not analyze(text,compiled)['pendientes']
    assert 'AMORTIGUADR' in text
    with pytest.raises(ValueError):rules.validate(dict(rules.EMPTY,reglas=[rule,rule]))
    with pytest.raises(ValueError):rules.validate(dict(rules.EMPTY,reglas=[dict(rule,expresion='juego',corregida='buje')]))
    with pytest.raises(ValueError):rules.validate(dict(rules.EMPTY,reglas=[dict(rule,expresion='AA111AA')]))
    with pytest.raises(ValueError):rules.validate(dict(rules.EMPTY,reglas=[dict(rule,corregida='persona privada')]))

def test_spelling_preserves_each_original_occurrence():
    r=analyze('TENSOR ISK; TENSOR IZQUIERDO; POSIBLE BARTA CORTA')
    assert r['pendientes']==['POSIBLE BARTA CORTA']
    words=[d['texto'] for d in r['descriptores']]
    assert 'ISK' in words and 'IZQUIERDO' in words

def test_kit_public_schema_is_strict():
    lines=[dict(linea=1,registros_periodo=1)]
    valid=kit_sube.aggregate([dict(linea=1,tiene_novedades=True,novedades='KIT')],lines)
    for key,value in [('version',True),('dominio','AA111AA'),('controles_con_incidencia',True)]:
        wrong=copy.deepcopy(valid);wrong[key]=value
        with pytest.raises(ValueError):kit_sube.validate(wrong,lines)
    wrong=copy.deepcopy(valid);wrong['lineas'][0]['linea']=True
    with pytest.raises(ValueError):kit_sube.validate(wrong,lines)

