"""Catálogo versionado y equivalencias confirmadas por FTR. Sin inferir gravedad.

Las reglas son datos separados del motor. Una futura edición administrativa
requerirá validación y una nueva versión; nunca reinterpreta archivos cerrados.
"""
VERSION = 4
# Contrato público compatible con Administración 06.3.6. La revisión del
# intérprete se registra por separado en los informes protegidos y en Git.
ENGINE_REVISION = 7
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
CATALOGUE_V3 = CATEGORIES
CATEGORIES = dict(CATALOGUE_V3, direccion=(*CATALOGUE_V3['direccion'][:-1], 'amortiguador_direccion', 'direccion_sin_componente'))
CATALOGUES = {1: LEGACY_CATEGORIES, 2: CATALOGUE_V3, 3: CATALOGUE_V3, 4: CATEGORIES}
POSITIONS = r'(?:delanter[oa]s?|traser[oa]s?)(?:\s+(?:derech[oa]s?|izquierd[oa]s?))?'
# No cruzar líneas, guiones ni palabras para fabricar un código. Se protege
# también el código no confirmado completo, para no reconocer un prefijo suyo.
CODE_GAP = r'(?:[ \t]*[.,-][ \t]*|[ \t]*)'
CODE_TOKEN = r'\b(?:p[ \t]*\.?[ \t]*[fs]|[ar])'+CODE_GAP+r'\d+(?:[.,]\d+)*\b'
A_CODE = r'a'+CODE_GAP+r'[1-8](?!\w|[.,]\d)'
PF_CODE = r'p[ \t]*\.?[ \t]*f'+CODE_GAP+r'[1-6](?!\w|[.,]\d)'
PS_CODE = r'p[ \t]*\.?[ \t]*s'+CODE_GAP+r'[1-4](?!\w|[.,]\d)'
R_CODE = r'r'+CODE_GAP+r'[1-8](?!\w|[.,]\d)'
# A number is positional only beside its explicit component family.
NAMED_FAMILIES = ((r'amortiguador(?:es)?','a',8),(r'pulmon(?:es)?\s+(?:de\s+)?frenos?','pf',6),
                  (r'pulmon(?:es)?\s+(?:de\s+)?suspension','ps',4),(r'neumaticos?','r',8))
NAMED_GAP = r'(?:[ \t]*[.-][ \t]*|[ \t]+)'
NAMED_CODE_TOKEN = r'\b(?:'+'|'.join(p for p,_,_ in NAMED_FAMILIES)+')'+NAMED_GAP+r'\d+(?:[.,]\d+)*\b'
def numbered(name, maximum):return name+'(?:'+NAMED_GAP+'[1-'+str(maximum)+r'](?!\w|[.,]\d))?'
# Un buje de amortiguador es un hallazgo de buje, salvo otra falla separada.
RULES = (
    ('bujes', r'(?:'+A_CODE+r'|amortiguador(?:es)?)(?:\s+'+POSITIONS+r')?\s+(?:con\s+)?bujes?|bujes?\s+(?:de|del)\s+(?:amortiguador(?:es)?|'+A_CODE+r')'),
    ('columna_direccion', r'columnas?\s+(?:de\s+)?direccion'),
    ('caja_direccion', r'cajas?\s+(?:de\s+)?direccion'),
    ('amortiguador_direccion', r'amortiguador(?:es)?\s+(?:de\s+)?direccion'),
    ('barra_corta', r'(?:barras?\s+)?cortas?\s+(?:(?:lado|extremo)\s+)?(?:pit+t?man|eje)\b'),
    ('brazo_pitman', r'(?:brazos?\s+)?pit+t?man'),
    ('rotulas_direccion', r'rotulas?(?:\s+(?:de\s+)?direccion)?'),
    ('barra_larga', r'(?:tensor(?:es)?\s+(?:de\s+(?:la\s+)?)?)?barras?\s+largas?'),
    ('barra_corta', r'(?:tensor(?:es)?\s+(?:de\s+(?:la\s+)?)?)?barras?\s+cortas?|corta(?=\s+(?:entera|delanter[oa])\b)'),
    ('flexibles_freno', r'flexibles?\s+(?:(?:de|del)\s+)?pulmon(?:es)?\s+(?:de\s+)?frenos?|flexibles?(?:\s+(?:(?:de|del)\s+)?frenos?)?'),
    ('pulmon_freno', numbered(r'pulmon(?:es)?\s+(?:(?:de|del)\s+)?frenos?',6)+'|'+PF_CODE+r'|pf(?![ \t]*[.,]?[ \t]*\d)'),
    ('tanque_aire', r'tanques?\s+(?:de\s+)?aire'),
    ('valvula_descarga', r'valvulas?\s+(?:de\s+)?descarga'),
    ('freno_servicio', r'frenos?\s+(?:de\s+)?servicio'),
    ('freno_estacionamiento', r'frenos?\s+(?:de\s+)?estacionamiento'),
    ('freno_emergencia', r'frenos?\s+(?:de\s+)?emergencia'),
    ('pulmon_suspension', numbered(r'pulmon(?:es)?\s+(?:de\s+)?suspension',4)+r'|pulmon(?:es)?|'+PS_CODE+r'|ps(?![ \t]*[.,]?[ \t]*\d)'),
    ('valvula_niveladora', r'valvulas?\s+niveladoras?'),
    ('barra_estabilizadora', r'barras?\s+estabilizadoras?'),
    ('tensores', r'tensor(?:es)?'),
    ('amortiguadores', numbered(r'amortiguador(?:es)?',8)+'|'+A_CODE),
    ('bujes', r'bujes?'),
    ('cardan', r'cardan(?:es)?'),
    ('crucetas', r'crucetas?'),
    ('tuercas_rueda', r'tuercas?\s+(?:de\s+)?ruedas?'),
    ('bulones_rueda', r'bulon(?:es)?\s+(?:de\s+)?ruedas?'),
    ('neumatico_sin_ubicacion', numbered(r'neumaticos?',8)+r'|cubiertas?|'+R_CODE),
    ('corte_corriente', r'corta\s*corrientes?|corte\s+(?:de\s+)?(?:bateria|corriente)'),
    ('sonora_marcha_atras', r'(?:(?:senal|alarma)\s+)?sonora\s+(?:de\s+)?marcha\s+atras|chicharra(?:\s+(?:de\s+)?marcha\s+atras)?'),
    ('direccion_sin_componente', r'direccion'),
    ('freno_sin_ubicacion', r'sistema\s+(?:de\s+)?frenos?|frenos?'),
    ('suspension_sin_componente', r'suspension'),
    ('transmision_sin_componente', r'transmision'),
    ('electrico_sin_componente', r'sistema\s+electrico'),
)
# Positions explicitly confirmed for revision 7. Unknown precision stays unknown.
def position(n):return ('delantero' if n<=2 else 'trasero')+(' izquierdo' if n%2 else ' derecho')
ALIASES = {**{f'r{n}': ('neumaticos_delanteros' if n<=2 else 'neumaticos_traseros',
    position(n)+(' interno' if n in (3,4) else ' externo' if n in (5,6) else '') if n<=6 else 'trasero') for n in range(1,9)},
    **{f'a{n}': ('amortiguadores',position(n) if n<=6 else 'sin_ubicacion') for n in range(1,9)},
    **{f'pf{n}': ('pulmon_freno',position(n)) for n in range(1,7)},
    **{f'ps{n}': ('pulmon_suspension',position(n)) for n in range(1,5)}}
