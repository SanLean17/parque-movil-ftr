"""Generación determinista del listado web desde la configuración central."""
import json
import re
from pathlib import Path
from .config import enabled


def update_public(root, config):
    root = Path(root)
    path = root/'index.html'
    s = path.read_text(encoding='utf-8')
    s, count = re.subn(r'const\s+lineas\s*=\s*\[[\s\S]*?\]\s*\.sort\(\s*\(a,\s*b\)\s*=>\s*a\s*-\s*b\s*\)\s*;', 'const lineas = '+json.dumps(sorted(enabled(config)))+';', s, count=1)
    if not count:
        s, count = re.subn(r'const\s+lineas\s*=\s*\[[\s\S]*?\]\s*;', 'const lineas = '+json.dumps(sorted(enabled(config)))+';', s, count=1)
    if not count:
        raise ValueError('No se reconoció el listado de líneas del index; publicación detenida.')
    if 'ftr-publica.js' not in s:
        s = s.replace('</body>', '<script src="ftr-publica.js?v=6"></script>\n</body>')
    path.write_text(s, encoding='utf-8')
    p = root/'linea.html'
    s = p.read_text(encoding='utf-8')
    if 'onclick="copyControlled()"' not in s:
        m = re.search(r'<button\s+onclick="copyMissing\(\)"[\s\S]*?</button>', s)
        if not m:
            raise ValueError('No se reconoció el botón de pendientes; publicación detenida.')
        original = m[0].replace('Copiar Faltantes', 'Copiar pendientes')
        second = original.replace('copyMissing()', 'copyControlled()').replace('Copiar pendientes', 'Copiar controlados')
        s = s[:m.start()]+'<div class="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">'+original+second+'</div>'+s[m.end():]
    if 'ftr-publica.js' not in s:
        s = s.replace('</body>', '<script src="ftr-publica.js?v=6"></script>\n</body>')
    p.write_text(s, encoding='utf-8')
