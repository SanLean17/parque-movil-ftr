"""Proyección pública mínima de controles válidos de una lectura ya realizada.

No lee fuentes. No publica nombres de pestañas, filas, novedades ni resultados.
Cada revisión conserva en Git el historial del período/fuente que la originó.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from .config import enabled


def write_history(root, config, events, read_utc, today):
    root=Path(root);lines=enabled(config);grouped=defaultdict(list)
    for event in events:
        date=event.get('fecha');line=event.get('linea');domain=event.get('dominio')
        if line in lines and domain and date and date.year==config['period'] and date<=today:
            grouped[line].append(dict(dominio=domain,fecha=date.isoformat(),interno=event.get('interno') or ''))
    folder=root/'historial';folder.mkdir(exist_ok=True)
    for line in lines:
        data=dict(version=1,linea=line,periodo=config['period'],lectura_planilla_utc=read_utc,
                  controles_sha256=hashlib.sha256((root/'controlados'/f'linea{line}.csv').read_bytes()).hexdigest(),
                  controles=sorted(grouped[line],key=lambda r:(r['dominio'],r['fecha'],r['interno'])))
        (folder/f'linea{line}.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
