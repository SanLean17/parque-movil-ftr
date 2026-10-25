import copy
import json
from datetime import date
import pytest
from _ftr_runtime.test_mechanical_review import ReviewTests
from _ftr_runtime import public_statistics as stats,statistics_archive as archive,mechanical_review as review
from _ftr_runtime import statistics_reinterpretation as revision,dictionary_rules as rules
from _ftr_runtime.legacy_mechanics import mechanics

def test_explicit_reinterpretation_preserves_controls_backups_and_active_year():
    t=ReviewTests();t.setUp()
    try:
        t.google(t.sheets());historical,_,detail=t.build();archive_path=t.root/'estadisticas/2025.json'
        capsule=detail['novedades_sin_clasificar']['revision_mecanica'];events=[dict(r,fecha=date.fromisoformat(r['fecha'])) for r in capsule['registros']]
        old=copy.deepcopy(historical);old.update(version=3,anomalias=mechanics(events,rules.EMPTY,8)[0]);old.pop('kit_sube')
        capsule.update(motor_revision=8,estadisticas=copy.deepcopy(old));review.unpack(capsule)
        from _ftr_runtime.historical_statistics import add_archive
        add_archive(t.root,old)
        (t.root/'_ftr_config.json').write_text(json.dumps(t.config),encoding='utf-8')
        (t.root/'ftr_publicacion.json').write_text(json.dumps(dict(files_sha256={})),encoding='utf-8')
        before={p.relative_to(t.root).as_posix():p.read_bytes() for p in t.root.rglob('*') if p.is_file()}
        proposal=revision.prepare(t.root,capsule)
        assert proposal['despues']['version']==4 and proposal['despues']['kit_sube']['controles_con_incidencia']==0
        assert all((t.root/p).read_bytes()==b for p,b in before.items())
        with pytest.raises(ValueError):revision.apply(t.root,capsule,dict(proposal['confirmation'],expected_records='0'*64))
        changed=revision.apply(t.root,capsule,proposal['confirmation'])
        for p,b in before.items():
            if p not in changed:assert (t.root/p).read_bytes()==b
        assert json.loads((t.root/stats.FILE).read_bytes())['periodo']==2026
        backup=t.root/f'estadisticas/revisiones/2025/{revision.digest(before["estadisticas/2025.json"])}.json'
        assert backup.read_bytes()==before['estadisticas/2025.json']
        new=stats.validate(json.loads(archive_path.read_bytes()));review.unchanged_controls(old,new);archive.validate_collection(t.root)
        assert new['anomalias']['motor_revision']==10
        with pytest.raises(ValueError):revision.apply(t.root,capsule,proposal['confirmation'])
        forged=copy.deepcopy(capsule);forged['registros'][0]['estado']='SIN NOVEDAD'
        with pytest.raises(ValueError):revision.prepare(t.root,forged)
    finally:t.tearDown()
