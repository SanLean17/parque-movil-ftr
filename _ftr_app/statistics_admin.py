"""Exploración local de informes protegidos y el único diccionario compartido."""
import base64
import copy
import hashlib
import json
import os
import secrets
import time
from _ftr_runtime import dictionary_rules as rules, mechanical_review as review
from _ftr_runtime import public_statistics as stats, statistics_archive as archive
from _ftr_runtime.config import clean_config,digest
from _ftr_runtime.statistics_commands import WORKFLOW
from _ftr_runtime.mechanical_dictionary import CATEGORIES, ENGINE_REVISION
from _ftr_runtime.technical_fields import INFORMATION
from _ftr_runtime import anomalies
from _ftr_runtime import record_interpretation as records
from _ftr_app.private_interpretations import Store

def install(server):
    store=Store(server);receipts={}
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
        views={};pending=[];saved=store.read()
        for year,value in reports().items():
            private=private_part(value);items=sorted(private.get('pendientes',[]),key=lambda x:(-x['frecuencia'],x['expresion']))
            capsule=private.get('revision_mecanica');summary=value.get('report') or {}
            local=None
            if capsule and cached and saved['registros']:
                try:
                    events,_,_,_=review.unpack(capsule)
                    applicable={}
                    for event in events:
                        key=records.reference(event)['registro_id'];decision=saved['registros'].get(key)
                        if decision and decision['huella']==records.correction(event,decision['fragmentos'])['huella']:applicable[key]=decision
                    if applicable:
                        from _ftr_runtime import legacy_anomalies_v5,legacy_anomalies_v6,legacy_anomalies_v7,legacy_anomalies_v8,legacy_anomalies_v9
                        previous={5:legacy_anomalies_v5,6:legacy_anomalies_v6,7:legacy_anomalies_v7,8:legacy_anomalies_v8,9:legacy_anomalies_v9}.get(capsule.get('motor_revision'),anomalies)
                        compiled=rules.compile_rules(capsule['diccionario'])
                        def local_analysis(event):
                            if records.reference(event)['registro_id'] in applicable:return records.apply(event,applicable,capsule['diccionario'])
                            return previous.analyze(event.get('novedades',''),compiled)
                        local,adjusted=stats.mechanics(events,dictionary=capsule['diccionario'],analyzer=local_analysis)
                        items=adjusted['pendientes']
                except ValueError:pass  # Un informe anterior no se reinterpreta silenciosamente.
            items=json.loads(json.dumps(items))
            # Local display-only comparison. Never saves classifications or updates sources.
            if cached:
                compiled=rules.compile_rules(cached['dictionary']);public=cached.get('statistics',{}).get(str(year),{})
                same_source=(public.get('lectura_planilla_utc')==summary.get('inicio_lectura_utc') or year<cached['period'] and (capsule or {}).get('sha256_archivo')==cached.get('hashes',{}).get(str(year)) and bool((capsule or {}).get('sha256_archivo')))
                verified=(public.get('interpretacion',{}).get('sha256')==cached['expected_dictionary'] and public.get('anomalias',{}).get('motor_revision')==ENGINE_REVISION and cached.get('publication',{}).get(str(year)) and same_source)
                for item in items:
                    unresolved=0;refs=item.get('referencias',[])
                    for ref in refs:
                        if not isinstance(ref.get('novedades_original'),str) or not ref['novedades_original'].strip():
                            unresolved+=1;continue
                        result=anomalies.analyze(ref.get('novedades_original',''),compiled);term=anomalies.fold(item['expresion'])
                        if any(term in anomalies.fold(p) or anomalies.fold(p) in term for p in result['pendientes']):unresolved+=1
                    solved=len(refs)-unresolved
                    color='verified' if refs and solved==len(refs) and verified else 'waiting' if solved else 'attention'
                    message='APLICADO Y VERIFICADO' if color=='verified' else ('INTERPRETACIÓN DISPONIBLE · '+str(solved)+' apariciones resueltas localmente; estadísticas pendientes'+(' · '+str(unresolved)+' ambiguas' if unresolved else '')) if solved else 'REQUIERE REVISIÓN · falta una interpretación inequívoca'
                    item['interpretacion']=dict(color=color,mensaje=message,resueltas=solved,ambiguas=unresolved)
            kit_details=[]
            if capsule:
                try:
                    from _ftr_runtime.kit_sube import detected
                    kit_details=[records.reference(e) for e in review.unpack(capsule)[0] if detected(e)]
                except ValueError:pass
            views[str(year)]=dict(pending=items,preview_available=bool(capsule),read=summary.get('inicio_lectura_utc'),
                                  historical=summary.get('historico',False),sheetUrl=(capsule or {}).get('sheetUrl'),archive=(capsule or {}).get('sha256_archivo'),local=local,kit=kit_details)
            pending.extend(items)
        saved=store.read()
        return server.jsonify(motor_revision=ENGINE_REVISION,informacion=INFORMATION,remote=cached,pending=pending,reviews=views,catalogue=CATEGORIES,runs=runs,
            particulares=dict(revision=saved['revision'],cantidad=len(saved['registros'])),descriptores=sorted(rules.DESCRIPTORS),significados=rules.MEANINGS,ubicaciones=records.LOCATIONS,defectos=records.DEFECTS)
    def context(body):
        year=body.get('period');cached=server.cached('diccionario_remoto.json',None)
        if not cached or type(year) is not int:raise ValueError('Consultá GitHub y elegí el período.')
        capsule=private_part(reports().get(year,{})).get('revision_mecanica')
        if not capsule:raise ValueError('Abrí el informe protegido de la última lectura para revisar los registros completos.')
        public=cached.get('statistics',{}).get(str(year))
        if not public:raise ValueError('No se verificó el período publicado.')
        if capsule.get('sha256_archivo'):
            if capsule['sha256_archivo']!=cached['hashes'][str(year)]:raise ValueError('El histórico cambió. Prepará nuevamente la revisión.')
        elif capsule['estadisticas']['lectura_planilla_utc']!=public['lectura_planilla_utc']:raise ValueError('Abrí el informe de la última publicación antes de continuar.')
        events,_,_,_=review.unpack(capsule);review.unchanged_controls(public,capsule['estadisticas'])
        return cached,capsule,events
    def selected(events,identifier):
        found=[e for e in events if records.reference(e)['registro_id']==identifier]
        if len(found)!=1:raise ValueError('No se pudo identificar un único registro. Abrí su informe actualizado.')
        return found[0]
    def record():
        try:
            body=server.request.get_json() or {};cached,capsule,events=context(body)
            event=selected(events,body.get('registro_id'));saved=store.read()['registros'].get(body['registro_id'])
            valid=saved and saved['huella']==records.correction(event,saved['fragmentos'])['huella']
            fragments=saved['fragmentos'] if valid else records.suggestions(event.get('novedades',''),cached['dictionary'])
            analysis=records.apply(event,store.read()['registros'],cached['dictionary'])
            return server.jsonify(registro=records.reference(event),fragmentos=fragments,analisis=analysis,
                fragmentos_analisis=[records.interpret(event['novedades'][f['inicio']:f['fin']], [dict(f,inicio=0,fin=f['fin']-f['inicio'])],cached['dictionary']) for f in fragments],guardada=bool(valid))
        except (ValueError,KeyError,TypeError):return server.jsonify(error='El registro necesita un informe completo y actualizado antes de interpretarlo.'),400
    def record_list():
        try:
            body=server.request.get_json() or {};_,_,events=context(body)
            term=str(body.get('search','')).casefold();offset=body.get('offset',0)
            if type(offset) is not int or offset<0:raise ValueError('Página no válida.')
            found=[records.reference(e) for e in events if term in e.get('novedades','').casefold() and e.get('novedades','').strip()]
            return server.jsonify(registros=found[offset:offset+20],total=len(found))
        except (ValueError,KeyError,TypeError) as error:return server.jsonify(error=str(error) if isinstance(error,ValueError) else 'Abrí un informe válido.'),400
    def record_preview():
        try:
            body=server.request.get_json() or {};cached,capsule,events=context(body)
            current=rules.validate(cached['dictionary']);saved=store.read()
            event=selected(events,body.get('registro_id'))
            correction=records.correction(event,body.get('fragmentos'),body.get('regla'),current)
            overrides=dict(saved['registros']);overrides[correction['registro_id']]=correction
            effect=review.preview(capsule,current,overrides)
            # El delta particular parte de las decisiones privadas ya guardadas.
            effect['antes']=stats.mechanics(events,dictionary=current,corrections=saved['registros'])[0]
            effect['motor_antes']=ENGINE_REVISION
            effect['afectados']=[]
            for item in events:
                before=records.apply(item,saved['registros'],current);after=records.apply(item,overrides,current)
                if before!=after:effect['afectados'].append(dict(records.reference(item),antes=before,despues=after))
            effect['ambiguos']=[]
            token=secrets.token_urlsafe(32)
            for key,value in list(receipts.items()):
                if value['expires']<time.monotonic():receipts.pop(key,None)
            if len(receipts)>=50:raise ValueError('Hay demasiadas vistas previas abiertas. Cerrá las anteriores e intentá nuevamente.')
            receipts[token]=dict(expires=time.monotonic()+300,period=body['period'],correction=correction,
                expected=review.fingerprint(saved),report=review.fingerprint(capsule),dictionary=rules.digest(current))
            return server.jsonify(dict(effect,confirmation=token,alcance='informe_privado'))
        except (ValueError,KeyError,TypeError) as error:return server.jsonify(error=str(error) if isinstance(error,ValueError) else 'Revisá los fragmentos.'),400
    def record_save():
        try:
            receipt=receipts.get((server.request.get_json() or {}).get('confirmation'))
            if not receipt or receipt['expires']<time.monotonic():raise ValueError('La vista previa venció. Calculala nuevamente.')
            cached,capsule,_=context(receipt)
            if review.fingerprint(capsule)!=receipt['report'] or rules.digest(cached['dictionary'])!=receipt['dictionary']:raise ValueError('Cambió el informe o el diccionario. Revisá nuevamente el impacto.')
            saved=store.save(receipt['correction'],receipt['expected'])
            return server.jsonify(guardada=True,revision=saved['revision'],aplicacion='informe_privado',publicacion_verificada=False)
        except (ValueError,KeyError,TypeError) as error:return server.jsonify(error=str(error) if isinstance(error,ValueError) else 'No se guardó la interpretación.'),400
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
            # A published recalculation can retain the same source timestamp.
            # Replay and prove that baseline; never label an older report delta
            # as a change from the newer published statistics.
            if public['anomalias']!=capsule['estadisticas']['anomalias']:
                candidates=[current,capsule['diccionario']]
                baseline=next((d for d in candidates if rules.digest(d)==public.get('interpretacion',{}).get('sha256')),None)
                if baseline is None or public['anomalias'].get('motor_revision')!=ENGINE_REVISION:
                    raise ValueError('La publicación usa otra interpretación. Abrí su informe protegido antes de calcular el impacto.')
                capsule=copy.deepcopy(capsule)
                capsule.update(motor_revision=ENGINE_REVISION,diccionario=baseline,estadisticas=copy.deepcopy(public))
                review.unpack(capsule)  # Requires exact aggregates from the same complete records.
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
    server.app.add_url_rule('/api/dictionary-record','dictionary_record',record,methods=['POST'])
    server.app.add_url_rule('/api/dictionary-records','dictionary_records',record_list,methods=['POST'])
    server.app.add_url_rule('/api/dictionary-record-preview','dictionary_record_preview',record_preview,methods=['POST'])
    server.app.add_url_rule('/api/dictionary-record-save','dictionary_record_save',record_save,methods=['POST'])
    def script():
        return server.app.response_class((server.RESOURCE/'panel-statistics-admin.js').read_text(encoding='utf-8'),mimetype='text/javascript')
    server.app.add_url_rule('/panel-statistics-admin.js','statistics_admin_script',script)
