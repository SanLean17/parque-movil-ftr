import copy
import unittest
from collections import Counter
from datetime import date
from estadisticas_periodo import clasificar_estado, completar_estadisticas, resumen_estadistico

DAY = date(2026, 10, 19)

def event(domain='ABC123', status='sinnovedad', number=2, dt=date(2026, 1, 2), internal='1', column=True):
    return dict(linea=number, dominio=domain, fecha=dt, interno=internal, estado=status, tiene_estado=column)

def fixture(evs, found=True):
    good = [e for e in evs if e['linea'] == 2 and e['fecha'] and e['fecha'].year == 2026 and e['fecha'] <= DAY and e['dominio']]
    pairs = Counter(e['dominio'] for e in good)
    row = dict(linea=2, parque_publicado=80, registros_periodo=len(good), dominios_unicos=len(pairs) if found else None,
               pestana_encontrada=found, repeticiones_adicionales=len(good)-len(pairs), unidades_repetidas=sum(n>1 for n in pairs.values()),
               fuera_de_servicio=sum(e['estado']=='fueradeservicio' for e in good), sin_novedad=sum(e['estado']=='sinnovedad' for e in good))
    return dict(periodo=2026, lineas=[copy.deepcopy(row)], estadisticas=[row], totales_estadisticas=dict(registros_validos=len(good), unidades_unicas_por_linea=len(pairs), repeticiones_adicionales=len(good)-len(pairs)))

class StatisticsTests(unittest.TestCase):
    def test_observado_recognized(self):
        e=[event(status='observado')]; r=completar_estadisticas(fixture(e),e,DAY)
        self.assertEqual(r['totales_estadisticas']['registros_observados'],1)
        self.assertEqual(r['estadisticas'][0]['estado_no_clasificado'],0)
    def test_observado_label_case(self):
        self.assertEqual(clasificar_estado(' OBSERVADO '),'observado')
    def test_no_inference_from_long_phrase(self):
        self.assertEqual(clasificar_estado('Observado pero sin verificar'),'estado_otro')
    def test_empty_and_other_separated(self):
        e=[event(status=''),event('DEF456','pendiente')]; r=completar_estadisticas(fixture(e),e,DAY)
        self.assertEqual(r['estadisticas'][0]['estado_vacio'],1); self.assertEqual(r['estadisticas'][0]['estado_otro'],1)
    def test_no_state_column_counted(self):
        e=[event(status='', column=False)]; r=completar_estadisticas(fixture(e),e,DAY)
        self.assertEqual(r['estadisticas'][0]['registros_sin_columna_estado'],1)
    def test_results_partition(self):
        e=[event(status=s) for s in ('fueradeservicio','observado','sinnovedad','','otro')]
        r=completar_estadisticas(fixture(e),e,DAY)['estadisticas'][0]
        self.assertEqual(sum(r[k] for k in ('fuera_de_servicio','observado','sin_novedad','estado_vacio','estado_otro')),5)
    def test_one_vehicle_eight_records(self):
        e=[event() for _ in range(8)]; r=completar_estadisticas(fixture(e),e,DAY)['estadisticas'][0]
        self.assertEqual(r['unidades_repetidas'],1);self.assertEqual(r['repeticiones_adicionales'],7)
    def test_two_repeated_three_additional(self):
        e=[event() for _ in range(3)]+[event('DEF456') for _ in range(2)]
        r=completar_estadisticas(fixture(e),e,DAY)['estadisticas'][0]
        self.assertEqual(r['unidades_repetidas'],2);self.assertEqual(r['repeticiones_adicionales'],3)
    def test_equal_only_when_two_per_vehicle(self):
        e=[event(),event(),event('DEF456'),event('DEF456')]
        r=completar_estadisticas(fixture(e),e,DAY)['estadisticas'][0]
        self.assertEqual(r['unidades_repetidas'],r['repeticiones_adicionales'])
    def test_historical_and_missing_internal_remain(self):
        e=[event('ZZZ999','observado',internal='')]; r=completar_estadisticas(fixture(e),e,DAY)
        self.assertEqual(r['totales_estadisticas']['registros_observados'],1)
    def test_invalid_dates_and_domains_not_counted(self):
        e=[event(domain=''),event(dt=None),event(dt=date(2027,1,1)),event(dt=date(2026,12,1)),event()]
        self.assertEqual(completar_estadisticas(fixture(e),e,DAY)['totales_estadisticas']['registros_validos'],1)
    def test_unconfigured_not_published(self):
        e=[event(number=75),event()];r=completar_estadisticas(fixture(e),e,DAY)
        self.assertEqual(r['totales_estadisticas']['registros_validos'],1)
    def test_no_table_is_unknown_not_zero(self):
        r=completar_estadisticas(fixture([],found=False),[],DAY)
        self.assertIsNone(r['estadisticas'][0]['observado'])
    def test_valid_empty_is_zero(self):
        r=completar_estadisticas(fixture([]),[],DAY)
        self.assertEqual(r['estadisticas'][0]['observado'],0)
    def test_mismatch_rejects(self):
        e=[event()];r=fixture(e);r['estadisticas'][0]['registros_periodo']=2
        with self.assertRaises(ValueError):completar_estadisticas(r,e,DAY)
    def test_no_private_plates_in_public_report(self):
        e=[event('ABC123','observado')];r=completar_estadisticas(fixture(e),e,DAY)
        self.assertNotIn('ABC123',str(r));self.assertNotIn('ABC123',resumen_estadistico(r))
    def test_fleet_context_preserved(self):
        e=[event()];r=completar_estadisticas(fixture(e),e,DAY)
        self.assertEqual(r['estadisticas'][0]['parque_publicado'],80)
        self.assertIn('Parque actual',resumen_estadistico(r))

if __name__=='__main__':unittest.main()
