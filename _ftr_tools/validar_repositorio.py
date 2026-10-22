"""Contratos estáticos y datos publicados; sin red ni escrituras."""
import ast
import hashlib
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml
import configuracion_lineas
from _ftr_runtime.config import load, enabled, digest
from _ftr_runtime.native_schedule import PATH, render, RECOVERY_PATH, render_recovery
from _ftr_runtime import oneoff


def main():
    config = load(ROOT)
    mapping = enabled(config)
    assert configuracion_lineas.LINEAS_EMPRESAS == mapping
    assert configuracion_lineas.EMPRESAS_CNRT == sorted(set(mapping.values()))
    assert (ROOT/PATH).read_text(encoding='utf-8-sig') == render(config)
    assert (ROOT/RECOVERY_PATH).read_text(encoding='utf-8-sig') == render_recovery()
    assert (ROOT/oneoff.WORKFLOW).read_text(encoding='utf-8-sig') == oneoff.render(oneoff.load(ROOT))
    def workflow(name):
        return yaml.load((ROOT/'.github/workflows'/name).read_text(encoding='utf-8-sig'), Loader=yaml.BaseLoader)
    parent, child = workflow('actualizar_parques.yml'), workflow('ftr_sincronizar.yml')
    extraordinary=workflow('ftr_extraordinarias.yml')
    recovery=workflow('ftr_recuperar_turnos.yml')
    assert recovery['on']['schedule']==[{'cron':'7,22,37,52 * * * *'}]
    assert 'push' not in recovery['on'] and 'concurrency' not in recovery
    assert recovery['jobs']['comprobar']['with']['action']=='recovery'
    assert child['permissions']['actions']=='read'
    assert 'push' not in extraordinary['on'] and 'concurrency' not in extraordinary
    assert extraordinary['jobs']['actualizar']['with']['action']=='oneoff'
    assert child['jobs']['actualizar']['env']['FTR_ACTION']=="${{ inputs.action || 'scheduled' }}"
    assert 'schedule' in parent['on'] or not any(config[k]['enabled'] for k in ('drive','cnrt'))
    assert 'push' not in parent['on'] and 'push' not in child['on']
    assert 'schedule' not in child['on'] and 'concurrency' not in parent
    assert child['concurrency']['cancel-in-progress'] == 'false'
    assert child['concurrency']['queue'] == 'max'
    assert set(child['on']['workflow_dispatch']['inputs']) == {'action','config_json','expected','request_id'}
    assert 'refs/heads/main' in child['jobs']['actualizar']['if']
    html = (ROOT/'index.html').read_text(encoding='utf-8')
    assert json.loads(re.search(r'const lineas = (\[.*?\]);', html)[1]) == sorted(mapping)
    manifest = json.loads((ROOT/'ftr_publicacion.json').read_text())
    assert manifest['config_digest'] == digest(config)
    from _ftr_runtime.public_statistics import FILE as STATISTICS, ASSETS, validate
    statistics = validate(json.loads((ROOT/STATISTICS).read_text(encoding='utf-8')))
    assert statistics['periodo'] == manifest['period']
    assert [r['linea'] for r in statistics['lineas']] == manifest['lines']
    assert set(ASSETS) <= manifest['files_sha256'].keys()
    from _ftr_runtime.statistics_archive import validate_collection
    archive=validate_collection(ROOT,lambda name:subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT))
    assert {r['archivo'] for r in archive['periodos']} <= manifest['files_sha256'].keys()
    for page in ('index.html','linea.html'):
        assert not re.search(r'(?:href|onclick)=[^>]*estadisticas\.html', (ROOT/page).read_text(encoding='utf-8'), re.I)
    for name, expected in manifest.get('files_sha256', {}).items():
        data = subprocess.check_output(['git','show','HEAD:'+name], cwd=ROOT)
        assert hashlib.sha256(data).hexdigest() == expected, 'Manifiesto desactualizado: '+name
    for number in mapping:
        for folder in ('parques','controlados'):
            file = ROOT/folder/f'linea{number}.csv'
            with file.open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.DictReader(stream)
                assert reader.fieldnames and 'dominio' in reader.fieldnames, file.name
                assert all(None not in row and None not in row.values() for row in reader), file.name
    tracked = subprocess.check_output(['git','ls-files'], cwd=ROOT, text=True, encoding='utf-8').splitlines()
    for name in tracked:
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text(encoding='utf-8-sig'), filename=name)
    subprocess.run(['git','diff','--exit-code','HEAD','--','.'], cwd=ROOT, check=True)
    print(f'Contratos válidos: {len(mapping)} líneas, {len(set(mapping.values()))} empresas; pruebas sin modificar archivos versionados.')


if __name__ == '__main__':
    main()
