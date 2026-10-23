"""Catálogo versionado y equivalencias confirmadas por FTR. Sin inferir gravedad.

Las reglas son datos separados del motor. Una futura edición administrativa
requerirá validación y una nueva versión; nunca reinterpreta archivos cerrados.
"""
VERSION = 3
# Contrato público compatible con Administración 06.3.6. La revisión del
# intérprete se registra por separado en los informes protegidos y en Git.
ENGINE_REVISION = 5
LEGACY_CATEGORIES = {
    'direccion': ('barra_larga', 'barra_corta', 'direccion_sin_componente'),
    'frenos': ('frenos_delanteros', 'frenos_traseros', 'flexibles_freno', 'freno_sin_ubicacion'),
    'suspension': ('amortiguadores', 'bujes', 'suspension_sin_componente'),
    'transmision': ('cardan', 'crucetas', 'transmision_sin_componente'),
    'otras': ('sin_clasificar',),
}
CATEGORIES = {
    'direccion': ('columna_direccion', 'caja_direccion', 'brazo_pitman', 'rotulas_direccion', 'barra_larga', 'barra_corta', 'direccion_sin_componente'),
    'frenos': ('frenos_delanteros', 'frenos_traseros', 'flexibles_freno', 'pulmon_freno', 'tanque_aire', 'valvula_descarga', 'freno_servicio', 'freno_estacionamiento', 'freno_emergencia', 'freno_sin_ubicacion'),
    'suspension': ('amortiguadores', 'bujes', 'pulmon_suspension', 'valvula_niveladora', 'barra_estabilizadora', 'tensores', 'suspension_sin_componente'),
    'transmision': LEGACY_CATEGORIES['transmision'],
    'neumaticos': ('neumaticos_delanteros', 'neumaticos_traseros', 'tuercas_rueda', 'bulones_rueda', 'neumatico_sin_ubicacion'),
    'electrico': ('corte_corriente', 'sonora_marcha_atras', 'electrico_sin_componente'),
    'otras': ('sin_clasificar',),
}
CATALOGUES = {1: LEGACY_CATEGORIES, 2: CATEGORIES, 3: CATEGORIES}
POSITIONS = r'(?:delanter[oa]s?|traser[oa]s?)(?:\s+(?:derech[oa]s?|izquierd[oa]s?))?'
# No cruzar líneas, guiones ni palabras para fabricar un código. Se protege
# también el código no confirmado completo, para no reconocer un prefijo suyo.
CODE_GAP = r'(?:[ \t]*[.,-][ \t]*|[ \t]*)'
CODE_TOKEN = r'\b(?:p[ \t]*\.?[ \t]*[fs]|[ar])'+CODE_GAP+r'\d+(?:[.,]\d+)*\b'
A_CODE = r'a'+CODE_GAP+r'[1-8](?!\w|[.,]\d)'
PF_CODE = r'p[ \t]*\.?[ \t]*f'+CODE_GAP+r'[1-6](?!\w|[.,]\d)'
PS_CODE = r'p[ \t]*\.?[ \t]*s'+CODE_GAP+r'[1-4](?!\w|[.,]\d)'
R_CODE = r'r'+CODE_GAP+r'[1-8](?!\w|[.,]\d)'
# Un buje de amortiguador es un hallazgo de buje, salvo otra falla separada.
RULES = (
    ('bujes', r'(?:'+A_CODE+r'|amortiguador(?:es)?)(?:\s+'+POSITIONS+r')?\s+(?:con\s+)?bujes?|bujes?\s+(?:de|del)\s+(?:amortiguador(?:es)?|'+A_CODE+r')'),
    ('columna_direccion', r'columnas?\s+(?:de\s+)?direccion'),
    ('caja_direccion', r'cajas?\s+(?:de\s+)?direccion'),
    ('brazo_pitman', r'(?:brazos?\s+)?pit+t?man'),
    ('rotulas_direccion', r'rotulas?(?:\s+(?:de\s+)?direccion)?'),
    ('barra_larga', r'(?:tensor(?:es)?\s+(?:de\s+(?:la\s+)?)?)?barras?\s+largas?'),
    ('barra_corta', r'(?:tensor(?:es)?\s+(?:de\s+(?:la\s+)?)?)?barras?\s+cortas?|corta(?=\s+(?:entera|delanter[oa])\b)'),
    ('pulmon_freno', r'pulmon(?:es)?\s+(?:(?:de|del)\s+)?frenos?|'+PF_CODE+r'|pf(?![ \t]*[.,]?[ \t]*\d)'),
    ('flexibles_freno', r'flexibles?(?:\s+(?:(?:de|del)\s+)?frenos?)?'),
    ('tanque_aire', r'tanques?\s+(?:de\s+)?aire'),
    ('valvula_descarga', r'valvulas?\s+(?:de\s+)?descarga'),
    ('freno_servicio', r'frenos?\s+(?:de\s+)?servicio'),
    ('freno_estacionamiento', r'frenos?\s+(?:de\s+)?estacionamiento'),
    ('freno_emergencia', r'frenos?\s+(?:de\s+)?emergencia'),
    ('pulmon_suspension', r'pulmon(?:es)?(?:\s+(?:de\s+)?suspension)?|'+PS_CODE+r'|ps(?![ \t]*[.,]?[ \t]*\d)'),
    ('valvula_niveladora', r'valvulas?\s+niveladoras?'),
    ('barra_estabilizadora', r'barras?\s+estabilizadoras?'),
    ('tensores', r'tensor(?:es)?'),
    ('amortiguadores', r'amortiguador(?:es)?|'+A_CODE),
    ('bujes', r'bujes?'),
    ('cardan', r'cardan(?:es)?'),
    ('crucetas', r'crucetas?'),
    ('tuercas_rueda', r'tuercas?\s+(?:de\s+)?ruedas?'),
    ('bulones_rueda', r'bulon(?:es)?\s+(?:de\s+)?ruedas?'),
    ('neumatico_sin_ubicacion', r'neumaticos?|cubiertas?|'+R_CODE),
    ('corte_corriente', r'corta\s*corrientes?|corte\s+(?:de\s+)?(?:bateria|corriente)'),
    ('sonora_marcha_atras', r'(?:(?:senal|alarma)\s+)?sonora\s+(?:de\s+)?marcha\s+atras|chicharra'),
    ('direccion_sin_componente', r'direccion'),
    ('freno_sin_ubicacion', r'frenos?'),
    ('suspension_sin_componente', r'suspension'),
    ('transmision_sin_componente', r'transmision'),
    ('electrico_sin_componente', r'sistema\s+electrico'),
)
ALIASES = {**{f'r{n}': ('neumaticos_delanteros' if n <= 2 else 'neumaticos_traseros',
    ('delantero izquierdo' if n == 1 else 'delantero derecho') if n <= 2 else f'trasero r{n}') for n in range(1,9)},
    **{f'a{n}': ('amortiguadores', ('delantero izquierdo' if n == 1 else 'delantero derecho') if n <= 2 else f'trasero a{n}' if n<=6 else 'sin_ubicacion') for n in range(1,9)},
    **{f'pf{n}': ('pulmon_freno', ('delantero izquierdo' if n == 1 else 'delantero derecho') if n <= 2 else f'trasero pf{n}') for n in range(1,7)},
    **{f'ps{n}': ('pulmon_suspension', ('delantero izquierdo' if n == 1 else 'delantero derecho') if n <= 2 else f'trasero ps{n}') for n in range(1,5)}}
# Confirmación específica del usuario; no inferir los demás códigos R.
ALIASES['r4'] = ('neumaticos_traseros', 'trasero derecho interno')
