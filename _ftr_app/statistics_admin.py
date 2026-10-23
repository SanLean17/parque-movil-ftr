"""Exploración local de informes protegidos y el único diccionario compartido."""
import base64
import hashlib
import json
import os
from _ftr_runtime import dictionary_rules as rules, mechanical_review as review
from _ftr_runtime import public_statistics as stats, statistics_archive as archive
from _ftr_runtime.config import clean_config,digest
from _ftr_runtime.statistics_commands import WORKFLOW
from _ftr_runtime.mechanical_dictionary import CATEGORIES

def install(server):
    def reports():
        found={};values=[server.diagnostic_cache()]
        for path in sorted(server.DATA.glob('historico-*.'+('dpapi' if os.name=='nt' else 'json'))):
            try:values.append(json.loads(server.protect(path.read_bytes(),True) if os.name=='nt' else path.read_bytes()))
            except Exception:continue
        for value in values:
            if not value:continue
            report=value.get('report') or {};private=private_part(value);year=report.get('periodo')
            if year is None and private.get('pendientes'):year=private['pendientes'][0]['periodo']
            if year and (year not in found or report.get('inicio_lectura_utc','')>(found[year].get('report') or {}).get('inicio_lectura_utc','')):
                found[year]=value
        return found
    def private_part(value):
        return (value.get('details') or {}).get('novedades_sin_clasificar') or {}
    def status():
        cached=server.cached('diccionario_remoto.json',None);runs=[]
        if server.request.args.get('remote')=='1':
            revision=server.api('GET','git/ref/heads/main')['object']['sha']
            def raw(path):
                value=server.api('GET','contents/'+path+'?ref='+revision)
                return base64.b64decode(value['content'])
            def read(path):return json.loads(raw(path))
            cfg=clean_config(read('_ftr_config.json'));dictionary=rules.validate(read(rules.FILE))
            index=archive.validate_index(read(stats.INDEX));public={};hashes={}
            for item in index['periodos']:
                content=raw(item['archivo'])
                if hashlib.sha256(content).hexdigest()!=item['sha256']:raise ValueError('La publicación estadística no coincide con su índice.')
                public[str(item['periodo'])]=stats.validate(json.loads(content));hashes[str(item['periodo'])]=item['sha256']
            cached=dict(dictionary=dictionary,expected_dictionary=rules.digest(dictionary),expected=digest(cfg),period=cfg['period'],
                        periods=[r['periodo'] for r in index['periodos']],statistics=public,hashes=hashes,revision=revision,publication={})
            # Un commit no demuestra que Pages ya lo sirva. Solo lectura pública.
            for year in public:
                try:
                    response=server.requests.get('https://sanlean.com.ar/parque-movil-ftr/estadisticas/'+year+'.json',timeout=10,headers={'Cache-Control':'no-cache'})
                    cached['publication'][year]=response.status_code==200 and hashlib.sha256(response.content).hexdigest()==hashes[year]
                except Exception:cached['publication'][year]=False
            server.write_json(server.DATA/'diccionario_remoto.json',cached)
            for run in server.api('GET','actions/workflows/'+WORKFLOW+'/runs?branch=main&per_page=12').get('workflow_runs',[]):
                runs.append(dict(id=run['id'],title=run.get('display_title',''),status=run['status'],conclusion=run.get('conclusion')))
            state=read('_ftr_estado.json')
            run_id=(state.get('drive') or {}).get('run_id')
            if str(run_id).isdigit():runs.insert(0,dict(id=int(run_id),title='Último informe de la lectura activa',status='completed',conclusion=(state.get('drive') or {}).get('status')))
            server.write_json(server.DATA/'revisiones_ejecuciones.json',runs)
        else:runs=server.cached('revisiones_ejecuciones.json',[])
        views={};pending=[]
        for year,value in reports().items():
            private=private_part(value);items=sorted(private.get('pendientes',[]),key=lambda x:(-x['frecuencia'],x['expresion']))
            capsule=private.get('revision_mecanica');summary=value.get('report') or {}
            views[str(year)]=dict(pending=items,preview_available=bool(capsule),read=summary.get('inicio_lectura_utc'),
                                  historical=summary.get('historico',False),sheetUrl=(capsule or {}).get('sheetUrl'),archive=(capsule or {}).get('sha256_archivo'))
            pending.extend(items)
        return server.jsonify(remote=cached,pending=pending,reviews=views,catalogue=CATEGORIES,runs=runs)
    def preview():
        try:
            body=server.request.get_json() or {};year=body.get('period');cached=server.cached('diccionario_remoto.json',None)
            if not cached or type(year) is not int:raise ValueError('Consultá GitHub y elegí el período.')
            capsule=private_part(reports().get(year,{})).get('revision_mecanica')
            if not capsule:raise ValueError('El informe anterior no contiene todos los datos. Abrí el informe de la próxima lectura automática o prepará una revisión histórica.')
            public=cached.get('statistics',{}).get(str(year))
            if not public:raise ValueError('No se verificó el período publicado.')
            if capsule.get('sha256_archivo'):
                if capsule['sha256_archivo']!=cached['hashes'][str(year)]:raise ValueError('El histórico cambió. Prepará nuevamente la revisión.')
            elif capsule['estadisticas']['lectura_planilla_utc']!=public['lectura_planilla_utc']:
                raise ValueError('El informe no corresponde a la última publicación. Abrí su informe protegido antes de continuar.')
            current=rules.validate(cached['dictionary'])
            candidate=current if body.get('mode')=='saved' else rules.proposed(current,body.get('reglas'),body.get('expected_dictionary'))
            effect=review.preview(capsule,candidate);review.unchanged_controls(public,capsule['estadisticas'])
            effect['antes']=public['anomalias'];effect['dictionary']=candidate
            if year<cached['period'] and capsule.get('sheetUrl'):
                effect['command']=dict(period=year,sheetUrl=capsule['sheetUrl'],allow_partial=public['calidad']['parcial'],
                    expected_archive=cached['hashes'][str(year)],expected_dictionary=rules.digest(candidate),
                    expected_records=effect['huella_registros'],expected_result=effect['huella_resultado'])
            return server.jsonify(effect)
        except (ValueError,KeyError,TypeError) as error:
            return server.jsonify(error=str(error) if isinstance(error,ValueError) else 'El informe no contiene datos completos para la vista previa.'),400
    server.app.add_url_rule('/api/statistics-admin','statistics_admin',status,methods=['GET'])
    server.app.add_url_rule('/api/statistics-preview','statistics_preview',preview,methods=['POST'])
    def script():
        return server.app.response_class((server.RESOURCE/'panel-statistics-admin.js').read_text(encoding='utf-8'),mimetype='text/javascript')
    server.app.add_url_rule('/panel-statistics-admin.js','statistics_admin_script',script)
