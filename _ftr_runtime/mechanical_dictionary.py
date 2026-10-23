"""Catálogo versionado y equivalencias confirmadas por FTR. Sin inferir gravedad.

Las reglas son datos separados del motor. Una futura edición administrativa
requerirá validación y una nueva versión; nunca reinterpreta archivos cerrados.
"""
VERSION = 3
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
# Un buje de amortiguador es un hallazgo de buje, salvo otra falla separada.
RULES = (
    ('bujes', r'(?:a[1-6]|amortiguador(?:es)?)(?:\s+'+POSITIONS+r')?\s+(?:con\s+)?bujes?|bujes?\s+(?:de|del)\s+(?:amortiguador(?:es)?|a[1-6])'),
    ('columna_direccion', r'columnas?\s+(?:de\s+)?direccion'),
    ('caja_direccion', r'cajas?\s+(?:de\s+)?direccion'),
    ('brazo_pitman', r'(?:brazos?\s+)?pit+t?man'),
    ('rotulas_direccion', r'rotulas?(?:\s+(?:de\s+)?direccion)?'),
    ('barra_larga', r'(?:tensor(?:es)?\s+(?:de\s+(?:la\s+)?)?)?barras?\s+largas?'),
    ('barra_corta', r'(?:tensor(?:es)?\s+(?:de\s+(?:la\s+)?)?)?barras?\s+cortas?'),
    ('pulmon_freno', r'pulmon(?:es)?\s+(?:(?:de|del)\s+)?frenos?|pf'),
    ('flexibles_freno', r'flexibles?(?:\s+(?:(?:de|del)\s+)?frenos?)?'),
    ('tanque_aire', r'tanques?\s+(?:de\s+)?aire'),
    ('valvula_descarga', r'valvulas?\s+(?:de\s+)?descarga'),
    ('freno_servicio', r'frenos?\s+(?:de\s+)?servicio'),
    ('freno_estacionamiento', r'frenos?\s+(?:de\s+)?estacionamiento'),
    ('freno_emergencia', r'frenos?\s+(?:de\s+)?emergencia'),
    ('pulmon_suspension', r'pulmon(?:es)?(?:\s+(?:de\s+)?suspension)?'),
    ('valvula_niveladora', r'valvulas?\s+niveladoras?'),
    ('barra_estabilizadora', r'barras?\s+estabilizadoras?'),
    ('tensores', r'tensor(?:es)?'),
    ('amortiguadores', r'amortiguador(?:es)?|a[1-6]'),
    ('bujes', r'bujes?'),
    ('cardan', r'cardan(?:es)?'),
    ('crucetas', r'crucetas?'),
    ('tuercas_rueda', r'tuercas?\s+(?:de\s+)?ruedas?'),
    ('bulones_rueda', r'bulon(?:es)?\s+(?:de\s+)?ruedas?'),
    ('neumatico_sin_ubicacion', r'neumaticos?|cubiertas?|r[1-8]'),
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
    **{f'a{n}': ('amortiguadores', ('delantero izquierdo' if n == 1 else 'delantero derecho') if n <= 2 else f'trasero a{n}') for n in range(1,7)}}
