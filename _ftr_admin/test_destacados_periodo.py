import unittest
from datetime import date
from destacados_periodo import lideres, agregar_destacados
D = date(2026,10,19)
def event(n=2,dom='ABC123',day=1,internal='9'):
    return {'linea':n,'dominio':dom,'fecha':date(2026,1,day),'interno':internal}
def report(events):
    return {'periodo':2026,'estadisticas':[{'linea':n,'registros_periodo':sum(bool(e['linea']==n and e['dominio'] and e['fecha'] and e['fecha'].year==2026 and e['fecha']<=D) for e in events),'pestana_encontrada':True,'fuera_de_servicio':0,'observado':0} for n in (2,17)]}
class RankTests(unittest.TestCase):
    def test_ties(self):
        self.assertEqual(lideres({2:3,17:3,9:1},'x')['lineas'],[2,17])
    def test_no_positive_has_no_winner(self):
        self.assertEqual(lideres({2:0,17:None},'x')['lineas'],[])
    def test_multiple_controls_same_date_one_visit(self):
        e=[event(),event(dom='DEF456')]; r=report(e); p={};agregar_destacados(r,p,e,D)
        self.assertEqual(r['destacados']['lineas_mas_visitadas']['cantidad'],1)
        self.assertEqual(r['destacados']['lineas_mas_controles']['cantidad'],2)
    def test_two_dates_two_visits(self):
        e=[event(),event(day=2)];r=report(e);agregar_destacados(r,{},e,D)
        self.assertEqual(r['destacados']['lineas_mas_visitadas']['cantidad'],2)
    def test_rank_control_distinct_from_visits(self):
        e=[event()]*4+[event(n=17,day=i) for i in (1,2,3)];r=report(e);agregar_destacados(r,{},e,D)
        self.assertEqual(r['destacados']['lineas_mas_controles']['lineas'],[2])
        self.assertEqual(r['destacados']['lineas_mas_visitadas']['lineas'],[17])
    def test_unit_ties_retained(self):
        e=[event(),event(),event(dom='DEF456'),event(dom='DEF456')];r=report(e);p={};agregar_destacados(r,p,e,D)
        self.assertEqual(len(p['destacados_unidades']['unidades']),2)
    def test_current_internal_not_inferred(self):
        e=[event(day=1,internal='1'),event(day=2,internal='2'),event(day=2,internal='3')];r=report(e);p={};agregar_destacados(r,p,e,D)
        self.assertEqual(p['destacados_unidades']['unidades'][0]['internos_ultimo_control'],['2','3'])
    def test_same_plate_different_line_separate(self):
        e=[event(),event(n=17)];r=report(e);p={};agregar_destacados(r,p,e,D)
        self.assertEqual(len(p['destacados_unidades']['unidades']),2)
    def test_invalid_period_future_missing_domain_excluded(self):
        e=[event()];a=event();a['fecha']=date(2027,1,1);b=event();b['fecha']=date(2026,12,1);c=event();c['fecha']=None;e += [a,b,c,event(dom=''),event(n=75)]
        r=report(e);agregar_destacados(r,{},e,D);self.assertEqual(r['destacados']['lineas_mas_controles']['cantidad'],1)
    def test_missing_table_unknown(self):
        r=report([]);r['estadisticas'][0]['pestana_encontrada']=False;agregar_destacados(r,{},[],D)
        self.assertIsNone(r['estadisticas'][0]['fechas_con_controles'])
    def test_empty_units_not_error(self):
        r=report([]);p={};agregar_destacados(r,p,[],D);self.assertEqual(p['destacados_unidades']['unidades'],[])
    def test_no_private_data_in_summary(self):
        e=[event(internal='123456')];r=report(e);p={};agregar_destacados(r,p,e,D)
        self.assertNotIn('ABC123',str(r));self.assertNotIn('123456',str(r));self.assertIn('ABC123',str(p))
    def test_count_mismatch_rejected(self):
        e=[event()];r=report([])
        with self.assertRaises(ValueError):agregar_destacados(r,{},e,D)
    def test_outcomes_rank_by_records_not_units(self):
        r=report([]);r['estadisticas'][0].update(fuera_de_servicio=4,observado=1);r['estadisticas'][1].update(fuera_de_servicio=1,observado=3);agregar_destacados(r,{},[],D)
        self.assertEqual(r['destacados']['lineas_mas_fuera_de_servicio']['lineas'],[2]);self.assertEqual(r['destacados']['lineas_mas_observados']['lineas'],[17])
if __name__=='__main__':unittest.main()
