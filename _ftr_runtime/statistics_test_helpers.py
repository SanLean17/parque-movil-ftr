"""Productor agregado ficticio para pruebas del coordinador, sin fuentes."""
from . import public_statistics as stats
from .config import enabled


def write_mock_statistics(root, config, read_utc):
    rows=[{k:line if k=='linea' else 0 for k in stats.LINE_FIELDS} for line in sorted(enabled(config))]
    report=dict(listo_para_revision_de_integracion=True,estadisticas_version=4,periodo=config['period'],
        estadisticas=rows,totales_estadisticas={k:0 for k in stats.TOTALS})
    data,_=stats.build(report,[],config,read_utc)
    stats.write(root,data)
