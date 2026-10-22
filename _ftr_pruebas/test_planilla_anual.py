"""Pruebas con datos ficticios; no red, Google ni credenciales."""
import io
import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from planilla_anual import (
    Sheet, DiagnosisError, analyze, blocks, parse_date, plate, title_lines,
    decode_xlsx, spreadsheet_id, read_csv_domains, add_comparison, markdown,
)

TODAY = date(2026, 10, 19)
CONFIG = {2: 2058, 17: 2024, 45: 2068, 70: 2080, 119: 2068, 154: 2068, 179: 9085}


def sheet_from_rows(name, rows, merges=None):
    return Sheet(name, {(r, c): v for r, row in enumerate(rows, 1) for c, v in enumerate(row, 1) if v is not None and v != ""}, merges or [])


def single(rows, number=2, name=None):
    return sheet_from_rows(name or f"Línea {number}", [[f"LINEA {number}"], [], ["FECHA", "N°", "DOMINIO", "INTERNO", "ESTADO"]] + rows, [(1, 1, 2, 3)])


class AnnualTests(unittest.TestCase):
    def test_single_and_latest_date(self):
        s = single([["10/6/2026", 1, "AB123CD", 17, "FUERA DE SERVICIO"], ["04/9/2026", 2, "ab-123 cd", 17, "SIN NOVEDAD"]])
        report, records = analyze([s], {2: 2058}, 2026, TODAY)
        self.assertEqual(report["estado"], "LECTURA_COMPLETA")
        self.assertEqual(report["lineas"][0]["repeticiones"], 1)
        self.assertEqual(records[2]["AB123CD"][0], date(2026, 9, 4))

    def test_blank_rows_and_numeric_internal_do_not_stop_reading(self):
        s = single([["1/1/2026", 1, "AB123CD", 17], [], [], [], [], ["2/1/2026", 2, "ABC123", 45]])
        report, records = analyze([s], {2: 2058}, 2026, TODAY)
        self.assertEqual(len(records[2]), 2)

    def test_multiple_lines_assign_per_row(self):
        s = sheet_from_rows("Línea 45/70/119/154/179", [["LINEA 45-70-119-154-179"], [], ["FECHA", "N°", "LINEA", "DOMINIO", "INTERNO"], ["8/7/2026", 1, 119, "AB123CD", 727], ["8/7/2026", 2, 45, "ABC123", 65], ["8/7/2026", 3, 179, "AD456EF", 640]])
        report, records = analyze([s], {k: CONFIG[k] for k in (45,70,119,154,179)}, 2026, TODAY)
        self.assertEqual(set(records[119]), {"AB123CD"})
        self.assertEqual(set(records[45]), {"ABC123"})
        self.assertEqual(set(records[179]), {"AD456EF"})
        self.assertEqual(report["lineas"][1]["dominios_unicos"], 0)
        self.assertEqual(report["estado"], "LECTURA_COMPLETA")

    def test_multiple_lines_require_column(self):
        s = sheet_from_rows("LINEA 45/70", [["FECHA", "DOMINIO", "INTERNO"], ["1/1/2026", "AB123CD", 1]])
        report, records = analyze([s], {45:2068,70:2080}, 2026, TODAY)
        self.assertFalse(records)
        self.assertIn("BLOQUE_MULTIPLE_SIN_COLUMNA_LINEA", report["avisos_por_tipo"])

    def test_missing_line_in_multiple_sheet_is_not_inferred(self):
        s = sheet_from_rows("LINEA 45/70", [["FECHA", "LINEA", "DOMINIO", "INTERNO"], ["1/1/2026", "", "AB123CD", 1]])
        report, records = analyze([s], {45:2068,70:2080}, 2026, TODAY)
        self.assertFalse(records)
        self.assertIn("FILA_SIN_LINEA", report["avisos_por_tipo"])

    def test_other_year_excluded(self):
        s = single([["1/1/2025", 1, "AB123CD", 201], ["1/1/2026", 2, "ABC123", 202]])
        report, records = analyze([s], {2:2058}, 2026, TODAY)
        self.assertEqual(set(records[2]), {"ABC123"})
        self.assertEqual(report["avisos_por_tipo"]["REGISTROS_OTRO_ANIO"], 1)

    def test_future_date_requires_review(self):
        report, records = analyze([single([["31/12/2026",1,"AB123CD",1]])], {2:2058}, 2026, TODAY)
        self.assertFalse(records)
        self.assertEqual(report["estado"], "REVISAR")

    def test_empty_is_valid_not_error(self):
        report, _ = analyze([single([])], {2:2058}, 2026, TODAY)
        self.assertEqual(report["estado"], "VACIA_VALIDA")
        self.assertEqual(report["lineas"][0]["dominios_unicos"], 0)

    def test_absent_sheet_is_unknown_not_zero(self):
        report, _ = analyze([single([])], {2:2058,17:2024}, 2026, TODAY)
        self.assertIsNone(report["lineas"][1]["dominios_unicos"])
        self.assertEqual(report["lineas_habilitadas_no_encontradas"], [17])

    def test_dashboard_not_double_counted(self):
        s = single([["1/1/2026",1,"AB123CD",1]])
        dashboard = single([["1/1/2026",1,"AB123CD",1]], name="Tablero de Control")
        report, _ = analyze([dashboard, s], {2:2058}, 2026, TODAY)
        self.assertEqual(report["lineas"][0]["registros_periodo"], 1)

    def test_only_tabs_starting_with_linea_are_read_in_any_position(self):
        for name in ('Linea 2', 'LINEA 2', 'Línea 2', 'línea 2', 'LINEAS 2'):
            with self.subTest(name=name):
                auxiliary = sheet_from_rows('Auxiliar', [['FECHA', 'DOMINIO', 'INTERNO'], ['incorrecta', 'incorrecta', 1]])
                copy = single([['1/1/2026', 1, 'ABC123', 1]], name='Resumen Linea 2')
                control = single([['1/1/2026', 1, 'AB123CD', 1]], name=name)
                report, records = analyze([auxiliary, copy, control], {2:2058}, 2026, TODAY)
                self.assertEqual(report['estado'], 'LECTURA_COMPLETA')
                self.assertEqual(set(records[2]), {'AB123CD'})
                self.assertEqual(report['pestanas_totales'], 3)
                self.assertEqual([s['tipo'] for s in report['pestanas']], ['pestana_auxiliar_ignorada', 'pestana_auxiliar_ignorada', 'tabla_control'])
                self.assertEqual(report['pestanas'][-1]['posicion'], 3)

    def test_auxiliary_cannot_satisfy_a_missing_line_or_replace_all_controls(self):
        auxiliary = single([], number=17, name='Resumen Linea 17')
        report, _ = analyze([single([]), auxiliary], {2:2058, 17:2024}, 2026, TODAY)
        self.assertEqual(report['lineas_habilitadas_no_encontradas'], [17])
        self.assertEqual(report['estado'], 'REVISAR')
        with self.assertRaises(DiagnosisError):
            analyze([auxiliary], {17:2024}, 2026, TODAY)

    def test_linea_table_errors_still_require_review_at_original_position(self):
        auxiliary = sheet_from_rows('Auxiliar', [['FECHA', 'DOMINIO', 'INTERNO']])
        broken = single([['incorrecta', 1, 'AB123CD', 1]])
        report, _ = analyze([auxiliary, broken], {2:2058}, 2026, TODAY)
        self.assertEqual(report['estado'], 'REVISAR')
        self.assertEqual(report['ubicaciones_a_revisar'], [{'codigo':'FECHA_O_DOMINIO_INVALIDO', 'pestana_posicion':2, 'fila':4, 'linea':2, 'campo_a_revisar':'fecha'}])

    def test_new_line_detected_not_auto_enabled(self):
        report, records = analyze([single([], number=2), single([["1/1/2026",1,"AB123CD",1]], number=36)], {2:2058}, 2026, TODAY)
        self.assertEqual(report["lineas_detectadas_no_habilitadas"], [36])
        self.assertNotIn(36, records)

    def test_date_formats(self):
        for value in ("2026-04-09 00:00:00", "9/4/2026", "09-04-2026", "9/4/26", "2026-04-09T23:00:00Z"):
            self.assertEqual(parse_date(value), date(2026,4,9))
        self.assertIsNone(parse_date("31/02/2026"))
        self.assertEqual(parse_date((date(2026,4,9)-date(1899,12,30)).days), date(2026,4,9))
        self.assertEqual(parse_date((date(2026,4,9)-date(1904,1,1)).days, True), date(2026,4,9))

    def test_merged_date_only_not_plain_empty(self):
        s = single([["1/1/2026",1,"AB123CD",201], [None,2,"ABC123",202], [None,3,"AD456EF",203]])
        s.merges.append((4,1,5,1))
        report, records = analyze([s], {2:2058}, 2026, TODAY)
        self.assertEqual(set(records[2]), {"AB123CD","ABC123"})
        self.assertEqual(report["ubicaciones_a_revisar"][0]["fila"], 6)

    def test_vertical_blocks(self):
        s = sheet_from_rows("LINEAS 2/17", [["LINEA 2"], ["FECHA","DOMINIO","INTERNO"], ["1/1/2026","AB123CD",17], ["LINEA 17"], ["FECHA","DOMINIO","INTERNO"], ["2/1/2026","ABC123",2]])
        report, records = analyze([s], {2:2058,17:2024}, 2026, TODAY)
        self.assertEqual(set(records[2]), {"AB123CD"})
        self.assertEqual(set(records[17]), {"ABC123"})
        self.assertFalse(report["ubicaciones_a_revisar"])

    def test_horizontal_blocks_no_cross_assignment(self):
        s = sheet_from_rows("LINEA 63/113", [["LINEA 63",None,None,None,"LINEA 113"], ["FECHA","DOMINIO","INTERNO",None,"FECHA","DOMINIO","INTERNO"], ["1/1/2026","AB123CD",95,None,"2/1/2026","ABC123",17]])
        report, records = analyze([s], {63:2037,113:2037}, 2026, TODAY)
        self.assertEqual(set(records[63]), {"AB123CD"})
        self.assertEqual(set(records[113]), {"ABC123"})

    def test_csv_delimiters_and_195_long_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"test.csv"
            p.write_text('dominio;linea;interno\nAB123CD;195, 2077IE, 2077OP11;1\n', encoding="utf-8-sig")
            self.assertEqual(read_csv_domains(p,195), {"AB123CD"})
            p.write_text('linea,fecha,dominio,interno\n195,01/01/2026,AB123CD,1\n', encoding="utf-8")
            self.assertEqual(read_csv_domains(p,195), {"AB123CD"})
            p.write_text('dominio,linea\nAB123CD,195,EXTRA\n', encoding="utf-8")
            with self.assertRaises(DiagnosisError): read_csv_domains(p,195)

    def test_comparison_and_privacy(self):
        report, records = analyze([single([["1/1/2026",1,"AB123CD",201],["2/1/2026",2,"ABC123",202]])],{2:2058},2026,TODAY)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"parques").mkdir(); (root/"controlados").mkdir()
            (root/"parques/linea2.csv").write_text("dominio,linea\nAB123CD,2\nAD456EF,2\n", encoding="utf-8")
            (root/"controlados/linea2.csv").write_text("dominio,linea\nAB123CD,2\nAE789GH,2\n", encoding="utf-8")
            add_comparison(report,records,root)
        row = report["lineas"][0]
        self.assertEqual(row["coinciden_parque"],1)
        self.assertEqual(row["no_en_parque"],1)
        self.assertEqual(row["solo_planilla"],1)
        self.assertEqual(row["solo_publicado"],1)
        output = markdown(report)+json.dumps(report)
        for domain in ("AB123CD","ABC123","AE789GH"):
            self.assertNotIn(domain,output)

    def test_sheet_id_validation(self):
        ident = "1rxhnmA9-fekE8QHPddoalPRK66sHxdKu9jk1R4-lAJk"
        self.assertEqual(spreadsheet_id(f"https://docs.google.com/spreadsheets/d/{ident}/edit?gid=123"),ident)
        with self.assertRaises(DiagnosisError): spreadsheet_id("https://otro.com/spreadsheets/d/"+ident)
        with self.assertRaises(DiagnosisError): spreadsheet_id("https://drive.google.com/drive/folders/"+ident)

    def test_no_recognized_table_is_error(self):
        with self.assertRaises(DiagnosisError): analyze([sheet_from_rows("LINEA 2",[["Cabecera rota"]])],{2:2058},2026,TODAY)

    def test_xlsx_shared_inline_numeric_and_formula_cache(self):
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            z.writestr("xl/workbook.xml",f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Linea 2" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels",'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/sharedStrings.xml",f'<sst xmlns="{ns}"><si><t>DOMINIO</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml",f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>LINEA 2</t></is></c></row><row r="3"><c r="A3" t="inlineStr"><is><t>FECHA</t></is></c><c r="B3" t="s"><v>0</v></c><c r="C3" t="inlineStr"><is><t>INTERNO</t></is></c></row><row r="4"><c r="A4"><f>1+46022</f><v>46023</v></c><c r="B4" t="inlineStr"><is><t>AB123CD</t></is></c><c r="C4"><v>201</v></c></row></sheetData><mergeCells count="1"><mergeCell ref="A1:C2"/></mergeCells></worksheet>')
        sheets = decode_xlsx(buf.getvalue())
        self.assertEqual(sheets[0].get(2,2),"LINEA 2")
        self.assertEqual(sheets[0].get(3,2),"DOMINIO")
        self.assertEqual(sheets[0].get(4,1),46023)
        report, records = analyze(sheets,{2:2058},2026,TODAY)
        self.assertEqual(len(records[2]),1)

    def test_title_parser_no_arbitrary_internal_numbers(self):
        self.assertEqual(title_lines("LÍNEA 45-70-119-154-179"),{45,70,119,154,179})
        self.assertEqual(title_lines("95"),set())
        self.assertEqual(title_lines("1/1/2026"),set())
        self.assertEqual(plate(" ab-123 cd "),"AB123CD")
        self.assertEqual(plate("dominio"),"")


if __name__ == "__main__":
    unittest.main()
