"""Regresiones observadas durante la primera prueba real; ejemplos ficticios."""
import unittest
from datetime import date
from planilla_anual import Sheet, analyze, title_lines


def table(name, title, rows):
    values = [[title], [], ['FECHA', 'N°', 'LÍNEA', 'DOMINIO', 'INTERNO']] + rows
    return Sheet(name, {(r,c):v for r,row in enumerate(values,1) for c,v in enumerate(row,1) if v is not None and v != ''})


class ExportTests(unittest.TestCase):
    def test_removed_slash_in_tab_does_not_discard_rows(self):
        sheet = table('LINEA 9158', 'LINEA 9/158', [['01/01/2026',1,9,'AB123CD',12],['01/01/2026',2,158,'ABC123',45]])
        report, records = analyze([sheet], {9:2062,158:2048}, 2026, date(2026,10,19))
        self.assertEqual(set(records[9]), {'AB123CD'})
        self.assertEqual(set(records[158]), {'ABC123'})
        self.assertFalse(report['ubicaciones_a_revisar'])

    def test_concatenated_title_is_not_fictitious_line(self):
        self.assertEqual(title_lines('LINEA 517479164177'), set())
        sheet = table('LINEA 517479164177', 'LINEA 517479164177', [['01/01/2026',1,51,'AB123CD',1],['01/01/2026',2,177,'ABC123',2]])
        report, records = analyze([sheet], {51:2079,177:2079}, 2026, date(2026,10,19))
        self.assertEqual(set(records), {51,177})
        self.assertEqual(report['lineas_detectadas_no_habilitadas'], [])

    def test_spaces_and_unicode_dashes(self):
        self.assertEqual(title_lines('LÍNEA 45 – 70 – 119'), {45,70,119})
        self.assertEqual(title_lines('LINEA 51 74 79 164 177'), {51,74,79,164,177})

    def test_explicit_row_line_not_duplicated_from_title(self):
        sheet = table('LINEA 45/70', 'LINEA 45/70', [['01/01/2026',1,45,'AB123CD',1]])
        report, records = analyze([sheet], {45:2068,70:2080}, 2026, date(2026,10,19))
        self.assertEqual(set(records[45]), {'AB123CD'})
        self.assertFalse(records.get(70))

    def test_unknown_row_line_is_reported_not_published(self):
        sheet = table('LINEA 32/75/128', 'LINEA 32/75/128', [['01/01/2026',1,75,'AB123CD',1]])
        report, records = analyze([sheet], {32:2048,128:2048}, 2026, date(2026,10,19))
        self.assertEqual(report['lineas_detectadas_no_habilitadas'], [75])
        self.assertFalse(records)


if __name__ == '__main__':
    unittest.main()
