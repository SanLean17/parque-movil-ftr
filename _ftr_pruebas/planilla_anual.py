"""Diagnóstico aislado de la planilla anual. Nunca publica ni escribe CSV.

Solo se exporta el archivo indicado, con drive.readonly. El XLSX permanece en
memoria. Los informes contienen cantidades y posiciones de errores, no patentes,
novedades, personas, direcciones ni el contenido de las credenciales.
"""
from __future__ import annotations
import ast
import csv
import io
import json
import os
import posixpath
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROOT = Path(__file__).resolve().parents[1]


class DiagnosisError(Exception):
    """Mensaje controlado, apto para un log público."""


def text(value):
    return "" if value is None else str(value).strip()


def norm(value):
    value = unicodedata.normalize("NFD", text(value)).lower()
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in value if not unicodedata.combining(c)))


def is_control_sheet(name):
    """Solo pestañas cuyo nombre comienza con Linea, sin distinguir acentos/caso."""
    name = unicodedata.normalize("NFD", text(name)).casefold()
    return "".join(c for c in name if not unicodedata.combining(c)).startswith("linea")


def plate(value):
    value = re.sub(r"[\s\-\u200b\ufeff]+", "", text(value))
    # Validar antes de upper(): ß y ſ pueden convertirse en letras ASCII.
    # Ñ conserva su evidencia en el diagnóstico y nunca se transforma en N.
    if not value.isascii():
        return ""
    value = value.upper()
    return value if re.fullmatch(r"(?:[A-Z]{3}[0-9]{3}|[A-Z]{2}[0-9]{3}[A-Z]{2})", value) else ""


def line_number(value):
    value = text(value)
    return int(float(value)) if re.fullmatch(r"\d+(?:\.0+)?", value) else None


def title_lines(value):
    value = "".join(c for c in unicodedata.normalize("NFD", text(value).upper()) if not unicodedata.combining(c))
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    # No convertir títulos exportados como 517479164177 en una línea inventada.
    match = re.search(r"\bLINEAS?\s*[:#-]?\s*(\d{1,4}(?!\d)(?:[\s/,;|\-]+\d{1,4}(?!\d))*)", value)
    return {int(n) for n in re.findall(r"\d+", match.group(1)) if int(n) > 0} if match else set()


def parse_date(value, epoch1904=False):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 1 <= value <= 200000:
            return date(1904, 1, 1) + timedelta(days=int(value)) if epoch1904 else date(1899, 12, 30) + timedelta(days=int(value))
        return None
    s = text(value)
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?", s)
    if match:
        y, m, d = map(int, match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})(?:\s+\d{1,2}:.*)?", s)
        if not match:
            return None
        d, m, y = map(int, match.groups())
        if y < 100:
            y += 2000
    try:
        return date(y, m, d)
    except ValueError:
        return None


def coordinate(address):
    m = re.fullmatch(r"([A-Z]+)([1-9]\d*)", address)
    if not m:
        raise DiagnosisError("El XLSX contiene una coordenada no reconocida.")
    col = 0
    for c in m[1]:
        col = col * 26 + ord(c) - 64
    return int(m[2]), col


@dataclass
class Sheet:
    name: str
    cells: dict
    merges: list = field(default_factory=list)
    epoch1904: bool = False

    def get(self, row, col):
        if (row, col) in self.cells:
            return self.cells[row, col]
        # Solo hereda celdas realmente combinadas; nunca rellena huecos sueltos.
        for r1, c1, r2, c2 in self.merges:
            if r1 <= row <= r2 and c1 <= col <= c2:
                return self.cells.get((r1, c1))
        return None


def decode_xlsx(data):
    """Lee valores/cachés Open XML. No ejecuta fórmulas, macros o vínculos."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DiagnosisError("La exportación no es un XLSX válido.") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > 5000 or sum(i.file_size for i in infos) > 160_000_000:
            raise DiagnosisError("La exportación excede los límites seguros de esta prueba.")
        def xml(path):
            payload = archive.read(path)
            if b"<!DOCTYPE" in payload or b"<!ENTITY" in payload:
                raise DiagnosisError("El XLSX contiene declaraciones XML no admitidas.")
            return ET.fromstring(payload)
        workbook = xml("xl/workbook.xml")
        prop = workbook.find("x:workbookPr", NS)
        epoch = prop is not None and prop.get("date1904") in {"1", "true"}
        relationships = xml("xl/_rels/workbook.xml.rels")
        targets = {r.get("Id"): r.get("Target") for r in relationships if r.get("TargetMode") != "External"}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(t.text or "" for t in si.findall(".//x:t", NS)) for si in xml("xl/sharedStrings.xml")]
        sheets = []
        for element in workbook.findall("x:sheets/x:sheet", NS):
            target = targets.get(element.get(REL))
            if not target:
                raise DiagnosisError("Falta una pestaña de la exportación.")
            path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target))
            if not path.startswith("xl/"):
                raise DiagnosisError("Ruta de pestaña no admitida.")
            root = xml(path)
            cells = {}
            for cell in root.findall("x:sheetData/x:row/x:c", NS):
                ref = cell.get("r")
                if not ref:
                    raise DiagnosisError("Celda sin coordenada en la exportación.")
                pos = coordinate(ref)
                if pos[0] > 100000 or pos[1] > 2048:
                    raise DiagnosisError("La pestaña excede los límites de filas/columnas de la prueba.")
                v = cell.find("x:v", NS)
                raw = v.text if v is not None else None
                typ = cell.get("t")
                if typ == "s" and raw is not None:
                    value = shared[int(raw)]
                elif typ == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//x:t", NS))
                elif typ == "e":
                    value = "#ERROR_FORMULA"
                elif raw is None:
                    value = "#FORMULA_SIN_CACHE" if cell.find("x:f", NS) is not None else None
                elif typ in {"str", "d"}:
                    value = raw
                elif typ == "b":
                    value = bool(int(raw))
                else:
                    try:
                        number = float(raw)
                        value = int(number) if number.is_integer() else number
                    except ValueError:
                        value = raw
                if value is not None and text(value) != "":
                    cells[pos] = value
                if len(cells) > 1_000_000:
                    raise DiagnosisError("Demasiadas celdas para una prueba segura.")
            merges = []
            for merge in root.findall("x:mergeCells/x:mergeCell", NS):
                a, b = merge.get("ref", "").split(":")
                r1, c1 = coordinate(a)
                r2, c2 = coordinate(b)
                merges.append((r1, c1, r2, c2))
            sheets.append(Sheet(element.get("name", ""), cells, merges, epoch))
        return sheets


HEADERS = {
    "fecha": {"fecha", "fechacontrol", "fechafiscalizacion"},
    "dominio": {"dominio", "patente", "dominiovehiculo"},
    "interno": {"interno", "nrointerno", "numerointerno"},
    "linea": {"linea", "nrolinea", "numerolinea"},
}


def blocks(sheet):
    rows = defaultdict(dict)
    for (r, c), value in sheet.cells.items():
        rows[r][c] = norm(value)
    found = []
    for r in sorted(rows):
        dates = sorted(c for c, v in rows[r].items() if v in HEADERS["fecha"])
        for idx, left in enumerate(dates):
            right = dates[idx + 1] - 1 if idx + 1 < len(dates) else max(rows[r])
            columns = {}
            for kind, aliases in HEADERS.items():
                candidates = [c for c, v in rows[r].items() if left <= c <= right and v in aliases]
                if len(candidates) == 1:
                    columns[kind] = candidates[0]
            if not {"fecha", "dominio", "interno"} <= columns.keys():
                continue
            end_col = max(columns.values())
            identities = set()
            for rr in range(r - 1, max(0, r - 20), -1):
                ids = set()
                for c in range(left, end_col + 1):
                    ids |= title_lines(sheet.get(rr, c))
                if ids:
                    identities = ids
                    break
            tab_ids = title_lines(sheet.name)
            if not identities:
                identities = tab_ids
            conflict = bool(identities and tab_ids and not identities <= tab_ids)
            found.append({"row": r, "left": left, "right": end_col, "cols": columns, "ids": identities, "conflict": conflict})
    return found


def analyze(sheets, configured, year, today=None):
    today = today or datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    records = defaultdict(dict)
    occurrences = Counter()
    present, unknown = set(), set()
    issues, details = [], []
    counts, notes = Counter(), Counter()

    def issue(code, tab, row=0, line=None, reason=None):
        counts[code] += 1
        if len(issues) < 100:
            item = {"codigo": code, "pestana_posicion": tab, "fila": row}
            if line is not None:
                item["linea"] = line
            if reason:
                item["campo_a_revisar"] = reason
            issues.append(item)

    for tab, sheet in enumerate(sheets, 1):
        if not is_control_sheet(sheet.name):
            kind = "tablero_ignorado" if norm(sheet.name) == "tablerodecontrol" else "pestana_auxiliar_ignorada"
            details.append({"posicion": tab, "tipo": kind})
            continue
        found = blocks(sheet)
        ids = title_lines(sheet.name)
        if not found:
            header_kinds = {kind for kind, aliases in HEADERS.items()
                            if any(norm(v) in aliases for v in sheet.cells.values())}
            if ids or len(header_kinds & {'fecha', 'dominio', 'interno', 'linea'}) >= 2:
                issue("ENCABEZADOS_NO_ENCONTRADOS", tab)
            elif any(text(v) for v in sheet.cells.values()):
                notes['PESTANA_SIN_TABLA_RECONOCIDA'] += 1
            details.append({"posicion": tab, "tipo": "sin_tabla", "lineas": sorted(ids)})
            continue
        valid, counted_blocks = 0, 0
        sheet_lines = set()
        for block in found:
            expected, cols = block["ids"], block["cols"]
            by_row = "linea" in cols
            if not by_row and len(expected) != 1:
                if expected:
                    issue("BLOQUE_MULTIPLE_SIN_COLUMNA_LINEA", tab, block["row"])
                else:
                    issue("TABLA_SIN_IDENTIDAD", tab, block["row"])
                continue
            if block["conflict"]:
                if by_row:
                    # La identidad de cada fiscalización la define su columna LÍNEA.
                    notes["TITULO_PESTANA_DIFIERE_USA_COLUMNA_LINEA"] += 1
                else:
                    issue("TITULO_Y_PESTANA_NO_COINCIDEN", tab, block["row"])
                    continue
            counted_blocks += 1
            present |= expected & set(configured)
            unknown |= expected - set(configured)
            sheet_lines |= expected
            end = min((b["row"] for b in found if b["row"] > block["row"] and b["left"] <= block["right"] and b["right"] >= block["left"]), default=max((r for r, _ in sheet.cells), default=0) + 1)
            for row in range(block["row"] + 1, end):
                values = {k: sheet.get(row, c) for k, c in cols.items()}
                if not any(text(values.get(k)) for k in ("fecha", "dominio", "interno")):
                    continue
                if any(title_lines(sheet.cells.get((row, c))) for c in range(block["left"], block["right"] + 1)) and not plate(values.get("dominio")):
                    break
                number = line_number(values.get("linea")) if by_row else next(iter(expected))
                if number is None:
                    issue("FILA_SIN_LINEA", tab, row)
                    continue
                if by_row and expected and number not in expected:
                    notes["LINEA_EXPLICITA_DIFIERE_DEL_TITULO"] += 1
                sheet_lines.add(number)
                if number not in configured:
                    unknown.add(number)
                    counts["REGISTROS_LINEA_NO_HABILITADA"] += 1
                    continue
                present.add(number)
                parsed_date = parse_date(values.get("fecha"), sheet.epoch1904)
                if parsed_date is not None and parsed_date.year != year:
                    counts["REGISTROS_OTRO_ANIO"] += 1
                    continue
                domain = plate(values.get("dominio"))
                if parsed_date is None or not domain:
                    issue("FECHA_O_DOMINIO_INVALIDO", tab, row, number, "fecha" if parsed_date is None else "dominio")
                    continue
                if parsed_date > today:
                    issue("FECHA_FUTURA", tab, row, number, "fecha")
                    continue
                internal = text(values.get("interno"))
                if not internal:
                    issue("INTERNO_AUSENTE", tab, row, number, "interno")
                occurrences[number] += 1
                valid += 1
                prior = records[number].get(domain)
                if prior is None or parsed_date > prior[0]:
                    records[number][domain] = (parsed_date, internal)
        details.append({"posicion": tab, "tipo": "tabla_control" if counted_blocks else "tabla_sin_identidad_omitida", "bloques": counted_blocks, "lineas": sorted(sheet_lines), "registros_validos": valid})
    if not any("bloques" in d for d in details):
        raise DiagnosisError("No se reconoció ninguna tabla de fiscalizaciones; no se interpreta como cero controles.")
    result = {
        "modo": "DIAGNOSTICO_SIN_PUBLICAR", "periodo": year,
        "pestanas_totales": len(sheets), "pestanas": details,
        "lineas_habilitadas_no_encontradas": sorted(set(configured) - present),
        "lineas_detectadas_no_habilitadas": sorted(unknown),
        "avisos_por_tipo": dict(counts), "notas_de_formato": dict(notes),
        "ubicaciones_a_revisar": issues, "lineas": [],
    }
    for number in sorted(configured):
        values = records.get(number, {})
        result["lineas"].append({"linea": number, "empresa": configured[number], "pestana_encontrada": number in present,
            "registros_periodo": occurrences[number], "dominios_unicos": len(values) if number in present else None,
            "repeticiones": occurrences[number] - len(values),
            "ultima_fecha": max((v[0] for v in values.values()), default=None).isoformat() if values else None})
    result["estado"] = "REVISAR" if issues or result["lineas_habilitadas_no_encontradas"] else ("VACIA_VALIDA" if not sum(occurrences.values()) else "LECTURA_COMPLETA")
    return result, records


def read_csv_domains(path, number):
    if not path.exists():
        return None
    data = path.read_bytes()
    try:
        data = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        data = data.decode("cp1252")
    first = next((s for s in data.splitlines() if s.strip()), "")
    if not first:
        raise DiagnosisError("Un CSV publicado está vacío y sin encabezados; comparación detenida.")
    delimiter = max((";", ",", "\t"), key=lambda sep: len(next(csv.reader([first], delimiter=sep))))
    reader = csv.DictReader(io.StringIO(data), delimiter=delimiter, strict=True)
    keys = {norm(k): k for k in (reader.fieldnames or [])}
    domain_key = next((keys[k] for k in HEADERS["dominio"] if k in keys), None)
    line_key = keys.get("linea")
    if not domain_key:
        raise DiagnosisError("Un CSV publicado no tiene columna dominio; comparación detenida.")
    result = set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise DiagnosisError("Un CSV publicado tiene filas desalineadas; no se omiten silenciosamente.")
        if line_key and text(row[line_key]):
            tokens = {line_number(p.strip()) for p in re.split(r"[,;/|]", row[line_key])}
            if number not in tokens:
                continue
        domain = plate(row[domain_key])
        if domain:
            result.add(domain)
    return result


def add_comparison(report, records, root):
    for item in report["lineas"]:
        number = item["linea"]
        new = set(records.get(number, {}))
        fleet = read_csv_domains(root / "parques" / f"linea{number}.csv", number)
        old = read_csv_domains(root / "controlados" / f"linea{number}.csv", number)
        item.update({
            "parque_publicado": len(fleet) if fleet is not None else None,
            "controlados_publicados": len(old) if old is not None else None,
            "coinciden_parque": len(new & fleet) if fleet is not None and item["pestana_encontrada"] else None,
            "no_en_parque": len(new - fleet) if fleet is not None and item["pestana_encontrada"] else None,
            "solo_planilla": len(new - old) if old is not None and item["pestana_encontrada"] else None,
            "solo_publicado": len(old - new) if old is not None and item["pestana_encontrada"] else None,
        })


def configuration(root):
    # El diagnóstico participa del sistema activo: nunca una segunda lista.
    if (root / '_ftr_config.json').exists():
        sys.path.insert(0, str(ROOT))
        from _ftr_runtime.config import load, enabled
        return enabled(load(root))
    # Compatibilidad con fixtures y respaldos anteriores al panel.
    tree = ast.parse((root / "configuracion_lineas.py").read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LINEAS_EMPRESAS" for t in node.targets):
            raw = ast.literal_eval(node.value)
            return {int(k): int(v) for k, v in raw.items()}
    raise DiagnosisError("No se encontró la configuración de líneas.")


def source_settings(root):
    """Los diagnósticos usan la fuente publicada salvo una propuesta explícita."""
    sys.path.insert(0, str(ROOT))
    from _ftr_runtime.config import load
    config = load(root)
    year = int(os.environ.get('FTR_PERIODO') or config['period'])
    if not 2000 <= year <= 2100:
        raise DiagnosisError('El período está fuera del rango admitido.')
    identifier = spreadsheet_id(os.environ.get('FTR_SHEET_URL') or config['sheetUrl'])
    return year, identifier


def spreadsheet_id(value):
    if re.fullmatch(r"[A-Za-z0-9_-]{20,100}", value):
        return value
    parsed = urlparse(value)
    match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]{20,100})(?:/.*)?", parsed.path)
    if parsed.scheme != "https" or parsed.hostname != "docs.google.com" or not match:
        raise DiagnosisError("El enlace debe ser el de una hoja de Google Sheets.")
    return match[1]


def export_sheet(identifier):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    import google_auth_httplib2
    import httplib2
    try:
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise DiagnosisError("No está disponible el Secret GOOGLE_SERVICE_ACCOUNT_JSON en esta ejecución.")
        try:
            info = json.loads(raw)
            credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as exc:
            raise DiagnosisError("La credencial del bot no pudo cargarse. No publiques su contenido.") from exc
        http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=60))
        drive = build("drive", "v3", http=http, cache_discovery=False)
        fields = "mimeType,version,modifiedTime,capabilities(canDownload)"
        before = drive.files().get(fileId=identifier, fields=fields, supportsAllDrives=True).execute(num_retries=3)
        if before.get("mimeType") != "application/vnd.google-apps.spreadsheet":
            raise DiagnosisError("El enlace no identifica una hoja nativa de Google Sheets.")
        if before.get("capabilities", {}).get("canDownload") is False:
            raise DiagnosisError("La cuenta tiene acceso, pero el archivo no permite exportar a lectores.")
        buffer = io.BytesIO()
        download = MediaIoBaseDownload(buffer, drive.files().export_media(fileId=identifier, mimeType=XLSX), chunksize=1024 * 1024)
        finished = False
        while not finished:
            _, finished = download.next_chunk(num_retries=3)
            if buffer.tell() > 11_000_000:
                raise DiagnosisError("La exportación supera el límite de tamaño de esta prueba.")
        after = drive.files().get(fileId=identifier, fields=fields, supportsAllDrives=True).execute(num_retries=3)
        if before.get("version") != after.get("version") or before.get("modifiedTime") != after.get("modifiedTime"):
            raise DiagnosisError("La planilla cambió durante la lectura. Reintentá cuando no se esté editando.")
        return buffer.getvalue()
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        if status == 404:
            raise DiagnosisError("Google no encuentra la hoja para esta cuenta. Revisá el enlace y que el correo completo del bot sea Lector.") from exc
        if status == 403:
            raise DiagnosisError("Google rechazó la lectura o exportación (403). Revisá acceso de Lector, permiso para descargar y el límite de exportación de 10 MB. No requiere edición.") from exc
        raise DiagnosisError(f"Google no pudo completar la lectura (HTTP {status}). Reintentá la prueba; producción no fue modificada.") from exc


def markdown(report):
    s = ["# Prueba de planilla anual FTR", "", "**Solo lectura. No publica CSV, no llama a CNRT ni cambia la fuente activa.**", ""]
    if "error" in report:
        return "\n".join(s + ["## Lectura no completada", report["error"], "", "Ningún error se convierte en cero controlados."])
    s += [f"Estado: **{report['estado']}**. Período: **{report['periodo']}**. Pestañas examinadas: **{report['pestanas_totales']}**.",
        "", "Pestaña encontrada pero vacía = 0. Pestaña ausente = sin determinar, NO cero.", "",
        "| Línea | Registros | Dominios únicos | Repetidos | Coinciden con parque | Fuera del parque | Publicados | Solo planilla | Solo publicado |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in report["lineas"]:
        fields = ["linea", "registros_periodo", "dominios_unicos", "repeticiones", "coinciden_parque", "no_en_parque", "controlados_publicados", "solo_planilla", "solo_publicado"]
        s.append("| " + " | ".join("—" if item.get(k) is None else str(item[k]) for k in fields) + " |")
    s += ["", "## Estructura detectada", "| Posición de pestaña | Tipo | Líneas del encabezado | Bloques | Registros válidos |", "|---|---|---|---:|---:|"]
    for tab in report["pestanas"]:
        s.append(f"| {tab['posicion']} | {tab['tipo']} | {', '.join(map(str, tab.get('lineas', []))) or '—'} | {tab.get('bloques', '—')} | {tab.get('registros_validos', '—')} |")
    for key, label in [("lineas_habilitadas_no_encontradas", "Líneas habilitadas sin tabla reconocida"), ("lineas_detectadas_no_habilitadas", "Líneas detectadas aún no habilitadas")]:
        s += ["", f"**{label}:** " + (", ".join(map(str, report[key])) or "ninguna")]
    if report.get("notas_de_formato"):
        s += ["", "## Notas de interpretación", "```json", json.dumps(report["notas_de_formato"], ensure_ascii=False, indent=2), "```"]
    if report["avisos_por_tipo"]:
        s += ["", "## Avisos", "```json", json.dumps(report["avisos_por_tipo"], ensure_ascii=False, indent=2), "```"]
    if report["ubicaciones_a_revisar"]:
        s += ["", "## Ubicaciones a revisar (hasta 100; sin contenido de las celdas)", "```json", json.dumps(report["ubicaciones_a_revisar"], ensure_ascii=False, indent=2), "```"]
    s += ["", "No aparecer en el parque comparado NO demuestra una baja: puede ser transferencia, dato distinto o desfase de las fuentes.",
          "Los dominios, responsables, direcciones, novedades y claves NO forman parte de este informe.", "La comparación usa los CSV de la revisión GitHub de esta prueba, no una descarga nueva de CNRT."]
    return "\n".join(s)


def main():
    started = datetime.now(timezone.utc).isoformat()
    report = {}
    failed = False
    try:
        year, identifier = source_settings(ROOT)
        sheets = decode_xlsx(export_sheet(identifier))
        report, records = analyze(sheets, configuration(ROOT), year)
        add_comparison(report, records, ROOT)
        failed = bool(report["ubicaciones_a_revisar"])
    except DiagnosisError as exc:
        report = {"modo": "DIAGNOSTICO_SIN_PUBLICAR", "estado": "ERROR", "error": str(exc)}
        failed = True
    except Exception as exc:
        report = {"modo": "DIAGNOSTICO_SIN_PUBLICAR", "estado": "ERROR", "error": f"No se completó la prueba ({type(exc).__name__}). No se modificó producción."}
        failed = True
    report["inicio_lectura_utc"] = started
    report["fin_prueba_utc"] = datetime.now(timezone.utc).isoformat()
    report["revision_repositorio"] = os.environ.get("GITHUB_SHA", "local")
    summary = markdown(report)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary + "\n")
    directory = Path(os.environ.get("FTR_REPORTE_DIR", str(Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "ftr-prueba-planilla"))).resolve()
    if directory == ROOT or ROOT in directory.parents:
        raise DiagnosisError("El informe debe guardarse fuera del repositorio.")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "resumen.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "resumen.md").write_text(summary + "\n", encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
