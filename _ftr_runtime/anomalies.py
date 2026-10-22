"""Reglas explícitas v1. No deduce ESTADO, gravedad ni abreviaturas.

El texto original solo sale de este módulo hacia el informe cifrado. Los
identificadores de salida públicos pertenecen al catálogo fijo de abajo.
"""
import re
import unicodedata

VERSION = 1
CATEGORIES = {
    'direccion': ('barra_larga', 'barra_corta', 'direccion_sin_componente'),
    'frenos': ('frenos_delanteros', 'frenos_traseros', 'flexibles_freno', 'freno_sin_ubicacion'),
    'suspension': ('amortiguadores', 'bujes', 'suspension_sin_componente'),
    'transmision': ('cardan', 'crucetas', 'transmision_sin_componente'),
    'otras': ('sin_clasificar',),
}
# Términos solicitados, sin equivalencias técnicas inferidas. «Flexible» sin
# referencia explícita a freno queda sin clasificar.
RULES = (
    ('barra_larga', r'barras?\s+largas?'),
    ('barra_corta', r'barras?\s+cortas?'),
    ('flexibles_freno', r'flexibles?\s+(?:(?:de|del)\s+)?frenos?'),
    ('amortiguadores', r'amortiguador(?:es)?'),
    ('bujes', r'bujes?'),
    ('cardan', r'cardan(?:es)?'),
    ('crucetas', r'crucetas?'),
    ('direccion_sin_componente', r'direccion'),
    ('freno_sin_ubicacion', r'frenos?'),
    ('suspension_sin_componente', r'suspension'),
    ('transmision_sin_componente', r'transmision'),
)
PATTERN = re.compile('|'.join(r'\b(?P<'+key+'>'+pattern+r')\b' for key, pattern in RULES))
OWNER = {component: category for category, components in CATEGORIES.items() for component in components}
POSITION = re.compile(r'\b(?:delanter[oa]s?|traser[oa]s?)(?:\s+(?:derech[oa]s?|izquierd[oa]s?))?\b|\b(?:derech[oa]s?|izquierd[oa]s?)\b')
NEUTRAL = re.compile(r'^(?:sin\s+(?:novedad(?:es)?|anomalias?|fallas?|defectos?|observaciones?)|ok|s/?n|ningun[oa]?|[-.]+)$')
NEGATION = re.compile(r'\b(?:sin\s+(?:fallas?|defectos?|anomalias?|problemas?|novedades?)|no\s+(?:presenta|tiene|se\s+(?:detecta|observa))|en\s+buen\s+estado|ok)\b')
UNCERTAIN = re.compile(r'\b(?:posible|posiblemente|quizas?|duda|revisar|verificar|descartar|podria)\b|\?')
DEFECT = re.compile(r'\b(?:juego|rot[oa]s?|rotura|flojos?|flojas?|falla|fallas|defectuos[oa]s?|desgaste|perdida|perdidas|danad[oa]s?)\b')
DESCRIPTORS = re.compile(r'\b(?:y|e|de|del|la|el|los|las|en|con|un|una|por|al|se|su|sus|tiene|presenta|rot[oa]s?|rotura|flojos?|flojas?|juego|excesivo|excesiva|falla|fallas|defectuos[oa]s?|desgaste|perdida|perdidas|aceite|aire|danad[oa]s?|mal\s+estado)\b')


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').lower()) if not unicodedata.combining(c))


def classify(value):
    """Una mención por componente/ubicación en cada registro, sin doble keyword.

Las descripciones desconocidas se separan por cláusula, no por palabra. Una
negación o una descripción de normalidad nunca confirma una anomalía.
"""
    original = str(value or '').strip()
    if not original or NEUTRAL.fullmatch(fold(original)):
        return [], []
    findings, unknown = set(), []
    # Mantener «derecho e izquierdo» juntos; separar «frenos y cardán».
    clauses = re.split(r'[,;\n]+|\s+[ye]\s+(?=(?:'+ '|'.join(p for _, p in RULES) +r'|r\d+)\b)', fold(original))
    for clause in clauses:
        clause = clause.strip()
        if not clause or NEUTRAL.fullmatch(clause):
            continue
        matches = list(PATTERN.finditer(clause))
        if NEGATION.search(clause) or UNCERTAIN.search(clause):
            # No adivinar el alcance de una negación dentro de una cláusula.
            # Se conserva para revisión si no es una expresión neutral exacta.
            unknown.append(clause)
            continue
        remainder = list(clause)
        for index, match in enumerate(matches):
            component = match.lastgroup
            end = matches[index + 1].start() if index + 1 < len(matches) else len(clause)
            suffix = clause[match.end():end]
            locations = [m.group() for m in POSITION.finditer(suffix)] or ['sin_ubicacion']
            if component in ('direccion_sin_componente','suspension_sin_componente','transmision_sin_componente') and locations == ['sin_ubicacion'] and not DEFECT.search(clause):
                continue  # Un nombre genérico sin contexto puede no ser mecánico.
            axis = ''
            for location in locations:
                if location.startswith(('delanter','traser')):
                    axis = location.split()[0]
                elif axis and location.startswith(('derech','izquierd')):
                    location = axis+' '+location
                # La posición puede estar coordinada: «frenos delanteros y
                # traseros». Cada ubicación inequívoca pertenece a su componente.
                selected = component
                if component == 'freno_sin_ubicacion':
                    if location.startswith('delanter'): selected = 'frenos_delanteros'
                    elif location.startswith('traser'): selected = 'frenos_traseros'
                canonical = re.sub(r'delanter[oa]s?', 'delantero', location)
                canonical = re.sub(r'traser[oa]s?', 'trasero', canonical)
                canonical = re.sub(r'derech[oa]s?', 'derecho', canonical)
                canonical = re.sub(r'izquierd[oa]s?', 'izquierdo', canonical)
                findings.add((OWNER[selected], selected, canonical))
            remainder[match.start():match.end()] = ' ' * (match.end() - match.start())
        rest = ''.join(remainder)
        if matches:
            rest = POSITION.sub(' ', rest)
            rest = DESCRIPTORS.sub(' ', rest)
        rest = re.sub(r'[\s:./()\-]+', ' ', rest).strip()
        if rest:
            unknown.append(rest)
    return sorted(findings), sorted(set(unknown))
