"""Pantallas secundarias locales. Solo se envían reglas generales confirmadas."""
import base64
import json
from _ftr_runtime import dictionary_rules as rules
from _ftr_runtime.config import clean_config,digest
from _ftr_runtime.statistics_commands import WORKFLOW
from _ftr_runtime.mechanical_dictionary import CATEGORIES

def install(server):
    def pending():
        reports=[]
        current=server.diagnostic_cache()
        if current:reports.append(current)
        for path in sorted(server.DATA.glob('historico-*.dpapi')):
            try:reports.append(json.loads(server.protect(path.read_bytes(),True)))
            except Exception:continue
        values=[]
        for report in reports:
            private=(report.get('details') or {}).get('novedades_sin_clasificar',{})
            if isinstance(private,dict):values.extend(private.get('pendientes',[]))
        return values

    def status():
        cached=server.cached('diccionario_remoto.json',None)
        runs=[]
        if server.request.args.get('remote')=='1':
            revision=server.api('GET','git/ref/heads/main')['object']['sha']
            def read(path):
                value=server.api('GET','contents/'+path+'?ref='+revision)
                return json.loads(base64.b64decode(value['content']))
            config=clean_config(read('_ftr_config.json'));dictionary=rules.validate(read(rules.FILE))
            index=read('estadisticas/indice.json')
            cached=dict(dictionary=dictionary,expected_dictionary=rules.digest(dictionary),expected=digest(config),period=config['period'],periods=[r['periodo'] for r in index['periodos']])
            server.write_json(server.DATA/'diccionario_remoto.json',cached)
            for run in server.api('GET','actions/workflows/'+WORKFLOW+'/runs?branch=main&per_page=12').get('workflow_runs',[]):
                runs.append(dict(id=run['id'],title=run.get('display_title',''),status=run['status'],conclusion=run.get('conclusion')))
        return server.jsonify(remote=cached,pending=pending(),catalogue=CATEGORIES,runs=runs)
    server.app.add_url_rule('/api/statistics-admin','statistics_admin',status,methods=['GET'])
    def script():
        return server.app.response_class((server.RESOURCE/'panel-statistics-admin.js').read_text(encoding='utf-8'),mimetype='text/javascript')
    server.app.add_url_rule('/panel-statistics-admin.js','statistics_admin_script',script)
