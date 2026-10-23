(function(){
  'use strict';
  const style=document.createElement('style');
  style.textContent='#technicalDictionary select{height:var(--field-height);width:100%;min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-input);padding:0 16px;color:var(--text)}#technicalDictionary select:focus-visible{outline:3px solid var(--primary);outline-offset:3px}#technicalDictionary>summary,#historicalImporter>summary{cursor:pointer;min-height:36px}#technicalDictionary h3{margin-top:24px}#technicalDictionary .repeat-item{overflow-wrap:anywhere}';
  document.head.append(style);
  style.textContent+='#mechanicalReview select{height:var(--field-height);width:100%;background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:var(--radius-input);padding:0 12px}#mechanicalReview .stat{cursor:pointer;text-align:left;color:var(--text);font:inherit}#mechanicalReview .stat[aria-pressed=true]{border-color:var(--primary)}#mechanicalReview .repeat-item{overflow-wrap:anywhere}#mechanicalReview details>summary{cursor:pointer;min-height:44px;padding:10px 0}#mechanicalForm{margin-top:24px}#mechanicalReview select:focus-visible{outline:3px solid var(--primary);outline-offset:3px}';
  const q=id=>document.getElementById(id),csrf=document.querySelector('meta[name="ftr-csrf"]').content;
  const categories={direccion:'Dirección',frenos:'Sistema de frenos',suspension:'Suspensión',transmision:'Transmisión',neumaticos:'Neumáticos',electrico:'Sistema eléctrico',otras:'Otras / sin clasificar'};
  let data=null,editing=null;
  const label=x=>({sonora_marcha_atras:'Sonora de marcha atrás',corte_corriente:'Corte de batería / corriente',cardan:'Cardán',rotulas_direccion:'Rótulas de dirección',pulmon_freno:'Pulmón de freno',pulmon_suspension:'Pulmón de suspensión'}[x]||x.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()));
  function node(tag,text,cls){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
  async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'X-FTR-CSRF':csrf,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'No se pudo completar la operación.');return d;}
  function message(text,error=false){for(const id of ['technicalStatus','historicalStatus']){q(id).textContent=text;q(id).className=error?'error':'inline-note';}}
  function components(){const old=q('technicalComponent').value;q('technicalComponent').replaceChildren(...(data?.catalogue[q('technicalCategory').value]||[]).map(c=>new Option(label(c),c)));if([...q('technicalComponent').options].some(o=>o.value===old))q('technicalComponent').value=old;}
  function reset(){editing=null;q('technicalExpression').value='';q('technicalEnabled').checked=true;q('technicalPublic').checked=false;q('technicalSave').textContent='GUARDAR CLASIFICACIÓN';q('technicalSelection').textContent='Nueva equivalencia';}
  function edit(rule){editing=rule.expresion;q('technicalExpression').value=rule.expresion;q('technicalCategory').value=rule.categoria;components();q('technicalComponent').value=rule.componente;q('technicalEnabled').checked=rule.habilitada;q('technicalPublic').checked=false;q('technicalSave').textContent='MODIFICAR CLASIFICACIÓN';q('technicalSelection').textContent='Regla seleccionada: '+rule.expresion;}
  function render(){
    q('technicalCategory').replaceChildren(...Object.entries(categories).map(([id,name])=>new Option(name,id)));components();
    const list=q('technicalRules');list.replaceChildren();
    for(const r of data.remote?.dictionary.reglas||[]){const row=node('div',null,'repeat-item');row.append(node('strong',r.expresion+' · '+(r.habilitada?'CONFIRMADA':'DESHABILITADA')),node('p',categories[r.categoria]+' → '+label(r.componente),'small'));const b=node('button','Modificar','btn secondary');b.type='button';b.onclick=()=>edit(r);row.append(b);list.append(row);}
    if(!list.children.length)list.append(node('p','Sin equivalencias adicionales. El diccionario original sigue activo.','small'));
    const pending=q('technicalPending');pending.replaceChildren();
    for(const item of data.pending||[]){const row=node('details',null,'repeat-item');row.append(node('summary',item.expresion+' · '+item.frecuencia+' apariciones · '+item.periodo));row.append(node('p','PENDIENTE DE CLASIFICACIÓN','small'));for(const ref of (item.referencias||[]).slice(0,20))row.append(node('p','Línea '+ref.linea+' · Pestaña '+ref.pestana_posicion+': '+ref.pestana+' · Fila '+ref.fila,'small'));const b=node('button','Clasificar término técnico','btn secondary');b.type='button';b.onclick=()=>{reset();q('technicalExpression').value=/^(?:[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,24}|[A-Za-z]{1,4}\d{1,2})$/.test(item.expresion)?item.expresion:'';q('technicalSelection').textContent='Seleccionada: '+item.expresion+' · '+item.periodo;};row.append(b);pending.append(row);}
    if(!pending.children.length)pending.append(node('p','No hay expresiones pendientes en los informes protegidos cargados. Consultá el informe de una lectura o importación.','small'));
    const runs=q('historicalRuns');runs.replaceChildren();
    for(const run of data.runs||[]){if(!run.title.includes('history-import'))continue;const row=node('div',null,'repeat-item');row.append(node('p',run.title+' · '+(run.conclusion||run.status)));if(run.status==='completed'){const b=node('button','Abrir informe protegido','btn secondary');b.type='button';b.onclick=async()=>{try{const d=await api('report',{run_id:run.id});if(!d?.report)throw Error('Esta ejecución no generó un informe.');diagnosticReport=d.report;adminDetails=d.details;renderDiagnostic();renderIncidents();renderStatistics();showView('incidents');await load(false);}catch(e){message(e.message,true);}};row.append(b);}runs.append(row);}
    q('historyAvailable').textContent=data.remote?'Años archivados: '+data.remote.periods.join(', ')+' · Activo: '+data.remote.period:'Consultá GitHub antes de confirmar una importación.';
    renderAnomalies();
  }
  async function load(remote){try{data=await api('statistics-admin'+(remote?'?remote=1':''));render();reset();message(data.remote?'Diccionario revisión '+data.remote.dictionary.revision+'. Las equivalencias se aplican en próximas lecturas; los años cerrados se conservan.':'Consultá GitHub para cargar el diccionario compartido.');}catch(e){message(e.message,true);}}
  q('technicalRefresh').onclick=()=>load(true);q('historicalRefresh').onclick=()=>load(true);q('technicalCategory').onchange=components;
  q('technicalDiscard').onclick=()=>{reset();message('Se dejó sin clasificar. La expresión original sigue protegida en el informe.');};
  q('technicalForm').onsubmit=e=>{e.preventDefault();if(!data?.remote){message('Consultá GitHub primero.',true);return;}if(!q('technicalPublic').checked){message('Confirmá que es un término técnico general, sin datos privados.',true);return;}
    const expression=q('technicalExpression').value.trim();const rows=data.remote.dictionary.reglas.filter(r=>r.expresion!==editing);rows.push({expresion:expression,categoria:q('technicalCategory').value,componente:q('technicalComponent').value,habilitada:q('technicalEnabled').checked});
    openDialog('Guardar equivalencia técnica','Se guardará en el repositorio: '+expression+' → '+label(q('technicalComponent').value)+'. No se enviará la observación original ni se recalcularán años cerrados.','Guardar clasificación',async()=>{try{await api('submit',{action:'dictionary-save',expected:data.remote.expected,statistical:{expected_dictionary:data.remote.expected_dictionary,reglas:rows}});message('Orden guardada. Seguí su resultado en Actualizaciones y luego consultá el diccionario.');}catch(err){message('EN CONFLICTO / REVISAR: '+err.message,true);}});
  };
  q('historicalForm').onsubmit=e=>{e.preventDefault();if(!data?.remote){message('Consultá GitHub primero.',true);return;}const period=Number(q('historicalPeriod').value);if(period>=data.remote.period||data.remote.periods.includes(period)){message('Elegí un año anterior que todavía no esté archivado.',true);return;}
    openDialog('Importar estadísticas históricas','Se leerá únicamente la fuente indicada para '+period+'. No cambia la configuración, los controles activos ni CNRT. '+(q('historicalPartial').checked?'Autorizaste excluir registros inválidos y mostrar el histórico como parcial.':'La importación se detendrá si hay registros excluidos.'),'Importar año',async()=>{try{await api('submit',{action:'history-import',expected:data.remote.expected,statistical:{period,sheetUrl:q('historicalUrl').value.trim(),allow_partial:q('historicalPartial').checked}});message('Importación solicitada. Seguí el resultado en Actualizaciones; luego consultá GitHub para abrir su informe.');}catch(err){message(err.message,true);}});
  };

  const formal={fuera_de_servicio:'Fuera de servicio',observado:'Observado',sin_novedad:'Sin novedad',estado_vacio:'Sin estado',estado_otro:'Otro estado'};
  let selectedCategory='otras',previewGeneration=0;
  function selectedYear(){return Number(q('mechanicalPeriod').value);}
  function mechanicalMessage(text,error=false){q('mechanicalStatus').textContent=text;q('mechanicalStatus').className=error?'error':'inline-note';}
  function dateLabel(value){return value?new Intl.DateTimeFormat('es-AR',{dateStyle:'short',timeStyle:'short',timeZone:'America/Argentina/Buenos_Aires'}).format(new Date(value))+' · Argentina':'Fecha no disponible';}
  function distribution(states,total){return Object.entries(formal).map(([key,name])=>name+': '+(states?.[key]??'no disponible')+(Number.isInteger(states?.[key])&&total?' ('+(100*states[key]/total).toLocaleString('es-AR',{maximumFractionDigits:1})+' %)':'')).join(' · ');}
  function mechanicalComponents(){
    const old=q('mechanicalComponent').value;
    q('mechanicalComponent').replaceChildren(...(data?.catalogue[q('mechanicalCategory').value]||[]).filter(c=>c!=='sin_clasificar').map(c=>new Option(label(c),c)));
    if([...q('mechanicalComponent').options].some(o=>o.value===old))q('mechanicalComponent').value=old;
  }
  function resetMechanical(){
    previewGeneration++;
    q('mechanicalForm').hidden=true;q('mechanicalPreview').hidden=true;q('mechanicalPreview').replaceChildren();q('mechanicalMeaning').checked=false;
  }
  function renderAnomalies(){
    const select=q('mechanicalPeriod'),old=select.value;
    const years=[...new Set([...(data.remote?.periods||[]),...Object.keys(data.reviews||{}).map(Number)])].sort((a,b)=>b-a);
    select.replaceChildren(...years.map(year=>new Option(year,year)));
    select.value=years.includes(Number(old))?old:String(data.remote?.period||years[0]||'');
    const year=selectedYear(),publicData=data.remote?.statistics?.[year],a=publicData?.anomalias;
    q('mechanicalCategory').replaceChildren(...Object.entries(categories).filter(([k])=>k!=='otras').map(([id,name])=>new Option(name,id)));mechanicalComponents();
    const summary=q('mechanicalSummary');summary.replaceChildren();
    for(const [id,name] of Object.entries(categories)){
      const c=a?.categorias.find(c=>c.id===id),b=node('button',null,'stat');b.type='button';b.dataset.mechanicalCategory=id;b.setAttribute('aria-pressed',String(id===selectedCategory));
      b.append(node('span',name),node('strong',c?.cantidad??'—'));b.onclick=()=>{selectedCategory=id;renderAnomalies();if(id==='otras')q('mechanicalPending').open=true;};summary.append(b);
    }
    const detail=q('mechanicalComponents');detail.replaceChildren();
    const cat=a?.categorias.find(c=>c.id===selectedCategory);
    if(cat)for(const component of cat.componentes){const item=node('div',null,'repeat-item');item.append(node('strong',label(component.id)+' · '+(component.cantidad??'—')),node('p',distribution(component.estados,component.cantidad),'small'));detail.append(item);}
    const review=data.reviews?.[year];
    q('mechanicalRead').textContent='Estadística publicada: '+dateLabel(publicData?.lectura_planilla_utc)+'. Informe privado: '+dateLabel(review?.read)+'.';
    const revision=publicData?.interpretacion?.revision;
    const applied=publicData?.interpretacion?.sha256===data.remote?.expected_dictionary;
    mechanicalMessage(!publicData?'Consultá GitHub para verificar los períodos y cantidades.':
      (data.remote?.publication?.[year]?'Publicación web comprobada. ':'Versión guardada en GitHub; publicación web todavía no comprobada. ')+
      'Diccionario del período: '+(revision??'original')+'. '+(applied?'Coincide con el diccionario guardado.':year===data.remote.period?'Las nuevas equivalencias se aplicarán en la próxima lectura automática válida.':'El año cerrado solo cambia mediante una revisión histórica confirmada.'));
    q('mechanicalHistorical').hidden=!(year<data.remote?.period);
    if(review?.sheetUrl)q('mechanicalHistoryUrl').value=review.sheetUrl;
    renderPending();
    const runs=q('mechanicalRuns');runs.replaceChildren();
    for(const run of data.runs||[]){
      const row=node('div',null,'repeat-item');row.append(node('p',run.title+' · '+(run.conclusion||run.status),'small'));
      if(run.status==='completed'&&!run.title.includes('dictionary-save')){
        const b=node('button','Abrir informe protegido','btn secondary');b.type='button';b.onclick=async()=>{try{const d=await api('report',{run_id:run.id});if(!d?.report)throw Error('La ejecución no tiene un informe disponible.');await load(false);mechanicalMessage('Informe protegido cargado. Elegí su período para revisar las expresiones.');}catch(e){mechanicalMessage(e.message,true);}};row.append(b);
      }runs.append(row);
    }
    if(!runs.children.length)runs.append(node('p','Consultá GitHub para ver informes recientes.','small'));
  }
  function renderPending(){
    const year=selectedYear(),review=data.reviews?.[year];
    const all=review?.pending||(data.pending||[]).filter(x=>x.periodo===year);
    const search=q('mechanicalSearch').value.trim().toLocaleLowerCase('es'),state=q('mechanicalState').value;
    const items=all.filter(x=>x.expresion.toLocaleLowerCase('es').includes(search)&&(!state||(x.estados?.[state]||0)>0)).sort((a,b)=>b.frecuencia-a.frecuencia||a.expresion.localeCompare(b.expresion));
    const count=all.reduce((n,x)=>n+x.frecuencia,0);
    q('mechanicalPendingCount').textContent=all.length?count+' menciones · '+all.length+' expresiones agrupadas · '+items.length+' coinciden con el filtro. Pendientes de clasificación según el informe privado.':'No hay pendientes en el informe protegido cargado. Si la estadística pública muestra pendientes, abrí su informe; la ausencia del detalle no significa cero.';
    const list=q('mechanicalExpressions');list.replaceChildren();
    for(const item of items){
      const row=node('details',null,'repeat-item');row.append(node('summary',item.expresion+' · '+item.frecuencia+' apariciones'));
      row.append(node('p','PENDIENTE DE CLASIFICACIÓN · '+distribution(item.estados,item.frecuencia),'small'));
      const records=node('div');let shown=0;const more=node('button','Ver registros originales','btn secondary');more.type='button';
      more.onclick=()=>{const refs=item.referencias||[];for(const ref of refs.slice(shown,shown+20)){
        const r=node('div',null,'repeat-item');r.append(node('strong',item.expresion),node('p','Año '+item.periodo+' · Línea '+ref.linea+' · Fecha '+(ref.fecha||'no conservada en este informe')+' · Dominio '+(ref.dominio||'no conservado')+' · Interno '+(ref.interno??'no conservado'),'small'),node('p','Pestaña '+ref.pestana_posicion+': '+ref.pestana+' · Fila '+ref.fila,'small'),node('p','NOVEDADES: '+(ref.novedades_original??'No disponible'),'small'),node('p','ESTADO formal: '+(ref.estado_formal===undefined?'No conservado en este informe':ref.estado_formal||'Vacío'),'small'));records.append(r);
      }shown+=20;more.hidden=shown>=refs.length;more.textContent='Ver más registros ('+Math.max(0,refs.length-shown)+' restantes)';};
      const classify=node('button','Clasificar expresión','btn secondary');classify.type='button';classify.onclick=()=>{
        resetMechanical();q('mechanicalForm').hidden=false;q('mechanicalSelected').textContent=item.expresion+' · '+item.frecuencia+' menciones · '+year;
        q('mechanicalExpression').value=item.expresion.length<=48?item.expresion:'';q('mechanicalForm').scrollIntoView({block:'center'});q('mechanicalExpression').focus();
      };
      row.append(more,records,classify);list.append(row);
    }
  }
  function displayPreview(effect,confirm,title){
    mechanicalMessage('Vista previa calculada. Confirmá la operación para guardarla o cancelá sin cambios.');
    const box=q('mechanicalPreview');box.replaceChildren();box.hidden=false;
    box.append(node('strong','VISTA PREVIA · '+effect.periodo),node('p','Calculada desde '+effect.registros+' controles completos. Los resultados formales, vehículos y fechas se conservan.','small'));
    for(const [id,name] of Object.entries(categories)){
      const before=effect.antes.categorias.find(x=>x.id===id)?.cantidad,after=effect.despues.categorias.find(x=>x.id===id)?.cantidad;
      box.append(node('p',name+': '+before+' → '+after,'small'));
    }
    box.append(node('p','El motor aplica negaciones, contextos y deduplicación; la reducción de pendientes puede diferir de la frecuencia de la expresión.','small'));
    const ok=node('button',title,'btn');ok.type='button';ok.onclick=confirm;
    const cancel=node('button','CANCELAR','btn secondary');cancel.type='button';cancel.onclick=()=>{resetMechanical();mechanicalMessage('Cancelado. No se guardó ninguna regla ni se enviaron cambios.');};
    const actions=node('div',null,'actions');actions.append(ok,cancel);box.append(actions);box.scrollIntoView({block:'center'});
  }
  q('mechanicalRefresh').onclick=()=>load(true);
  q('mechanicalPeriod').onchange=()=>{q('mechanicalHistoryUrl').value='';resetMechanical();renderAnomalies();};
  q('mechanicalSearch').oninput=renderPending;q('mechanicalState').onchange=renderPending;q('mechanicalCategory').onchange=mechanicalComponents;
  q('mechanicalCancel').onclick=()=>{resetMechanical();mechanicalMessage('Cancelado. No se guardó ninguna regla.');};
  q('mechanicalForm').addEventListener('input',()=>{previewGeneration++;q('mechanicalPreview').hidden=true;q('mechanicalPreview').replaceChildren();});
  q('mechanicalForm').onsubmit=async e=>{
    e.preventDefault();
    try{
      if(!data?.remote)throw Error('Consultá GitHub primero.');
      const rule={expresion:q('mechanicalExpression').value.trim(),categoria:q('mechanicalCategory').value,componente:q('mechanicalComponent').value,habilitada:true};
      const rows=[...data.remote.dictionary.reglas,rule],expected=data.remote.expected,expectedDictionary=data.remote.expected_dictionary;
      const generation=++previewGeneration;
      const effect=await api('statistics-preview',{period:selectedYear(),reglas:rows,expected_dictionary:expectedDictionary});
      if(generation!==previewGeneration)return;
      displayPreview(effect,()=>openDialog('Confirmar regla general',rule.expresion+' → '+categories[rule.categoria]+' → '+label(rule.componente)+'. Se guardará para próximas lecturas automáticas. El histórico requiere una revisión explícita.','CONFIRMAR CLASIFICACIÓN',async()=>{
        try{await api('submit',{action:'dictionary-save',expected,statistical:{expected_dictionary:expectedDictionary,reglas:rows}});resetMechanical();mechanicalMessage('Orden de clasificación guardada. Todavía no cambió la web. Consultá GitHub para verificar la regla y su posterior aplicación.');}catch(err){mechanicalMessage(err.message,true);}
      }), 'CONFIRMAR CLASIFICACIÓN');
    }catch(err){mechanicalMessage(err.message,true);}
  };
  q('mechanicalPrepare').onclick=()=>{
    const year=selectedYear(),remote=data?.remote,publicData=remote?.statistics?.[year];
    if(!publicData||year>=remote.period){mechanicalMessage('Elegí un período histórico verificado.',true);return;}
    const payload={period:year,sheetUrl:q('mechanicalHistoryUrl').value.trim(),allow_partial:publicData.calidad?.parcial||false,expected_archive:remote.hashes[year],expected_dictionary:remote.expected_dictionary};
    openDialog('Preparar revisión histórica','Autorizás leer únicamente la planilla histórica indicada de '+year+' para generar un informe cifrado. No modifica estadísticas ni lee CNRT.','PREPARAR INFORME',async()=>{
      try{await api('submit',{action:'history-review',expected:remote.expected,statistical:payload});mechanicalMessage('Preparación solicitada. Cuando termine, consultá GitHub y abrí el informe protegido.');}catch(e){mechanicalMessage(e.message,true);}
    });
  };
  q('mechanicalRecalculate').onclick=async()=>{
    try{
      const generation=++previewGeneration;
      const effect=await api('statistics-preview',{period:selectedYear(),mode:'saved'});
      if(generation!==previewGeneration)return;
      if(!effect.command)throw Error('Prepará y abrí el informe histórico antes de recalcular.');
      const expected=data.remote.expected;
      displayPreview(effect,()=>openDialog('Recalcular histórico '+effect.periodo,'Autorizás una lectura exclusiva de la planilla histórica. Solo publicará este cambio si los registros y el resultado coinciden con la vista previa. Se conservará la versión anterior.','CONFIRMAR RECÁLCULO',async()=>{
        try{await api('submit',{action:'history-recalculate',expected,statistical:effect.command});resetMechanical();mechanicalMessage('Recálculo histórico solicitado. La publicación se confirmará al finalizar y verificar la web.');}catch(err){mechanicalMessage(err.message,true);}
      }), 'CONFIRMAR RECÁLCULO HISTÓRICO');
    }catch(err){mechanicalMessage(err.message,true);}
  };

  load(false);
})();
