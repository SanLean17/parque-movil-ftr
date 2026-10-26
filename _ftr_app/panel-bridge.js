/* Conexión 06.3.1. Solo órdenes confirmadas, nunca borradores automáticos. */
(async function () {
  'use strict';
  const csrf = document.querySelector('meta[name="ftr-csrf"]').content;
  let remoteDigest = null, online = false, authorized = false, refreshLock = false;
  let submitting = false, localDraft = false, lastReportRun = null, remoteRuns = [], orders = [];
  let lastRefresh = 0, queueError = null, queueInfo = {}, checkingQueue = false, allOrders = false;
  const checkedReports = new Set();
  let publishedOneoffs=null;
  const editingOneoff={drive:false,cnrt:false};
  const openStates = ['pending', 'authorization', 'sending', 'unknown', 'sent', 'conflict'];
  const captions = {'dictionary-save':'Guardar diccionario técnico','history-import':'Importar estadísticas históricas','history-review':'Preparar informe histórico','history-recalculate':'Recalcular histórico autorizado',config:'Guardar y publicar configuración', diagnostic:'Probar lectura sin publicar',
    drive:'Actualizar planilla anual FTR', cnrt:'Actualizar parque móvil', all:'Actualizar ambos procesos',
    'oneoff-set':'Programar actualización única','oneoff-cancel':'Cancelar actualización programada'};
  async function api(path, body) {
    const options = {method:body === undefined ? 'GET' : 'POST', headers:{'X-FTR-CSRF':csrf}, cache:'no-store'};
    if (body instanceof FormData) options.body = body;
    else if (body !== undefined) { options.headers['Content-Type']='application/json'; options.body=JSON.stringify(body); }
    const response = await fetch('/api/' + path, options);
    let data;
    try { data=await response.json(); } catch { throw Error('No se pudo comunicar con el programa local. Volvé a abrirlo.'); }
    if (!response.ok) {
      const error = Error(data.error || 'La operación no pudo completarse.'); error.code=data.code; throw error;
    }
    return data;
  }
  function model() { return {version:2, period:state.period, sheetUrl:state.sheetUrl, drive:state.drive,
    cnrt:state.cnrt, lines:state.lines, anchor:state.anchor, timezone:state.timezone}; }
  function fromRemote(c) { state={...initial(), ...c, events:state.events}; dirty=false; populate(); }
  function locks() {
    $$('[data-oneoff-submit],[data-oneoff-cancel]').forEach(b=>b.disabled=!remoteDigest||!publishedOneoffs||submitting);
    $$('[data-run],#previewSend,#testSheet,#sourceForm button[type="submit"],#schedulesForm button[type="submit"]')
      .forEach(b=>b.disabled=!remoteDigest || submitting);
    $('#connectionBadge').textContent=online?'CONECTADO':authorized?'SIN CONEXIÓN':'SIN AUTORIZACIÓN';
    $('#connectionBadge').className='badge '+(online?'good':'wait');
    const pending=orders.filter(r=>openStates.includes(r.status));
    $('#liveConnection').textContent = pending.length ?
      pending.length+' orden(es) pendientes o en ejecución. Revisá su estado y cancelación en Actualizaciones. Los borradores no se envían solos.' :
      online ? 'Conectado a GitHub. Las actualizaciones usan la configuración publicada; los cambios locales requieren Guardar y publicar.' :
      'Sin acceso a GitHub. Podés guardar borradores y confirmar órdenes con la última configuración consultada. Solo las órdenes confirmadas se enviarán al abrir el programa con conexión.';
    $('#offlineText').textContent=online?'GitHub disponible. Se comprueba la revisión remota antes de publicar.':
      'El borrador y las órdenes confirmadas se conservan en este equipo. Lo que no se envió todavía no está en GitHub.';
  }
  function showActivity() {
    const box=$('#cloudActivity'); box.replaceChildren();
    const visible=[...orders.filter(r=>openStates.includes(r.status)), ...orders.filter(r=>!openStates.includes(r.status)).slice(allOrders?0:-4).reverse()];
    for (const row of visible) {
      const p=el('p'); p.dataset.orderId=row.id;p.tabIndex=-1;p.style.overflowWrap='anywhere';p.onfocus=()=>p.style.outline='2px solid var(--primary)';p.onblur=()=>p.style.outline='';
      p.append(el('strong', (captions[row.action]||row.action)+(row.oneoff?' · '+row.oneoff.source.toUpperCase():'')+' · '+(row.label||row.message)));
      p.append(document.createElement('br'), el('span',localTime(row.created_at)+' · '+row.message,'small'));
      p.append(document.createElement('br'),el('span','Identificador: '+row.id,'small'));
      const closed={cancelled:'CANCELADA ANTES DEL ENVÍO',resolved:'CERRADA SIN CONFIRMAR',failed:'ERROR'};
      const phase=closed[row.status]||({pending:'PENDIENTE DE ENVÍO',authorization:'PENDIENTE DE AUTORIZACIÓN',conflict:'CONFLICTO · REVISAR ANTES DE ENVIAR',sending:'ENVIANDO',unknown:'ENVÍO INCIERTO'}[row.status])||(row.status==='completed'?(row.publication_verified?'PUBLICACIÓN VERIFICADA':row.effect==='dictionary'?'REGLA GUARDADA · CONSULTAR APLICACIÓN':'COMPLETADA'):row.status==='sent'?(row.run_status==='in_progress'?'EN EJECUCIÓN':row.run_id?'EJECUCIÓN EN ESPERA':'SOLICITUD ENVIADA'):'ESTADO NO RECONOCIDO · REVISAR');
      const phaseBadge=el('span',phase,'badge '+(row.status==='completed'&&row.publication_verified?'good':row.status==='failed'?'error':'wait'));phaseBadge.style.whiteSpace='normal';p.append(document.createElement('br'),phaseBadge);
      if(row.checks?.length){const evidence=el('details');evidence.append(el('summary','Ver comprobaciones conservadas'));for(const check of row.checks){const label=check.complete?'Búsqueda completa':'Búsqueda incompleta';evidence.append(el('p',localTime(check.checked_at)+' · '+label+' · '+(check.result==='not_found'?'Sin coincidencia exacta; esto no prueba rechazo.':check.result==='found'?'Ejecución localizada.':check.message||check.result),'small'));}p.append(evidence);}
      if (row.depends_on && openStates.includes(row.status)) p.append(document.createElement('br'),el('span','Depende de la configuración confirmada anterior.','small'));
      if (['pending','authorization','conflict'].includes(row.status)) {
        const cancel=el('button','Cancelar antes del envío','text-btn'); cancel.type='button';
        cancel.onclick=()=>openDialog('Cancelar orden pendiente','Solo cancela esta orden local. Si ya comenzó el envío, el programa lo indicará.','Cancelar orden',async()=>{
          try { await api('orders/cancel',{request_id:row.id}); await refreshOrders(); notify('Orden cancelada antes del envío.'); }
          catch(e) { notify(e.message); await refreshOrders(); }
        }); p.append(cancel);
      }
      if (row.url && /^https:\/\/github\.com\/SanLean17\/parque-movil-ftr\/actions\/runs\/\d+$/.test(row.url)) {
        const link=el('a','Ver ejecución','text-btn'); link.href=row.url; link.target='_blank'; link.rel='noopener noreferrer'; p.append(link);
      }
      box.append(p);
    }
    if(queueError) box.append(el('p',queueError,'small'));
    for (const run of remoteRuns.slice(0,4)) {
      const p=el('p'),link=el('a',run.label||'Detalle de ejecución','text-btn');
      if(/^https:\/\/github\.com\/SanLean17\/parque-movil-ftr\/actions\/runs\/\d+$/.test(run.url||''))link.href=run.url;
      link.target='_blank';link.rel='noopener noreferrer';
      const origin=run.event==='schedule'?'Automática':run.event==='workflow_dispatch'?'Solicitada desde el panel o GitHub':'Ejecución';
      p.append(link,document.createTextNode(' · '+origin+' · '+localTime(run.created_at)),document.createElement('br'),
        el('span',run.detail||'La fecha de última lectura indica qué datos están guardados.','small'));box.append(p);
    }
    if(!visible.length&&!remoteRuns.length&&!queueError)box.textContent='No hay órdenes locales. Conectá GitHub para consultar las ejecuciones.';
    renderQueueReview();
    locks();
    renderOneoffs();
  }
  async function refreshOrders() {
    try { const data=await api('orders'); orders=data.orders; queueError=data.error; queueInfo=data; }
    catch(e) { queueError=e.message; }
    showActivity();
  }
  function renderQueueReview() {
    const row=queueInfo.blocked,box=$('#queueReview');box.hidden=!row&&!queueInfo.paused;
    const pending=orders.filter(r=>openStates.includes(r.status)),empty=!row&&!pending.length;
    box.setAttribute('role',row?'alert':'status');box.style.borderColor=row?'var(--wait)':'var(--border)';
    $('#queueTitle').textContent=row?'LA COLA DE ACTUALIZACIONES NECESITA REVISIÓN':empty?'COLA PAUSADA · SIN ÓRDENES PENDIENTES':'COLA PAUSADA · ÓRDENES POR REVISAR';
    $('#queueReason').textContent=row?(captions[row.action]||row.action)+' · '+localTime(row.created_at)+' · Identificador: '+row.id+' · '+row.message:empty?'No hay órdenes pendientes ni bloqueadas. Las canceladas, cerradas y completadas se conservan en el historial. La pausa local no cambia las programaciones de GitHub.':pending.length+' orden(es) abiertas. Antes de continuar, revisá las solicitudes y sus dependencias.';
    $('#queuePendingList').replaceChildren();for(const order of pending){$('#queuePendingList').append(el('li',(captions[order.action]||order.action)+' · '+order.id+' · '+order.label+(order.depends_on?' · Depende de '+order.depends_on:''),'small'));}
    $('#queuePendingList').hidden=empty;$('#queuePending').textContent=empty?'VER HISTORIAL DE ÓRDENES':'REVISAR ÓRDENES PENDIENTES';
    const check=row?.checks?.at(-1);
    $('#queueEvidence').textContent=check?(check.complete?'Comprobación completa':'Comprobación incompleta')+' · '+(check.result==='not_found'?'No se encontró el identificador exacto. Esto no demuestra que GitHub rechazó el envío.':check.result==='found'?'Se encontró una ejecución; revisá su resultado.':check.message||'Revisá la evidencia.')+(check.note?' '+check.note:''):'Comprobar solo consulta GitHub: no envía ni repite órdenes.';
    $('#queueCheck').disabled=checkingQueue||!row||!['unknown','sent','sending'].includes(row.status);
    $('#queueBlocked').disabled=!row;$('#queueResolve').disabled=checkingQueue||!row?.resolution?.confirmation;
    for(const id of ['queueCheck','queueBlocked','queueResolve','queueEvidence'])$('#'+id).hidden=!row;
    $('#queuePaused').hidden=!queueInfo.paused||empty;$('#queueResume').hidden=!queueInfo.paused||empty;
    $('#queueResume').disabled=checkingQueue||!!row;
  }
  function focusOrders(identifier) {
    allOrders=true;showActivity();const target=identifier?document.querySelector('[data-order-id="'+identifier+'"]'):$('#cloudActivity');
    if(target){target.tabIndex=-1;target.scrollIntoView({behavior:'smooth',block:'center'});target.focus({preventScroll:true});}
  }
  $('#queueBlocked').onclick=()=>focusOrders(queueInfo.blocked?.id);
  $('#queuePending').onclick=()=>focusOrders();
  $('#ordersHistory').onclick=()=>focusOrders();
  $('#queueCheck').onclick=async()=>{
    const identifier=queueInfo.blocked?.id;if(!identifier||checkingQueue)return;
    checkingQueue=true;renderQueueReview();$('#queueEvidence').textContent='Consultando todas las páginas del intervalo de la orden…';
    try {await api('orders/check',{request_id:identifier});}catch(e){notify(e.message);}finally{checkingQueue=false;await refreshOrders();}
  };
  $('#queueResolve').onclick=()=>{
    const row=queueInfo.blocked;if(!row?.resolution?.confirmation)return;
    openDialog('Resolver orden no confirmada','Se comprobará GitHub otra vez. Si sigue sin confirmarse, esta orden quedará cerrada sin afirmar éxito ni rechazo y sin reenviarse. Se conservarán su identificador e historial. Las órdenes siguientes quedarán PAUSADAS hasta que las revises.','Cerrar sin reenviar',async()=>{
      checkingQueue=true;renderQueueReview();try{await api('orders/resolve',{request_id:row.id,confirmation:row.resolution.confirmation});notify('Orden conservada sin confirmar. Revisá las pendientes antes de continuar.');}catch(e){notify(e.message);}finally{checkingQueue=false;await refreshOrders();}
    });
  };
  $('#queueResume').onclick=()=>{
    const confirmation=queueInfo.confirmation;
    const pending=orders.filter(r=>openStates.includes(r.status));if(!pending.length)return;
    const detail=pending.map((r,i)=>(i+1)+'. '+(captions[r.action]||r.action)+' · '+r.id+(r.depends_on?' · Depende de '+r.depends_on:'')).join('\n');
    openDialog('Continuar con las órdenes revisadas',pending.length+' orden(es) abiertas:\n'+detail+'\nLas pendientes podrán enviarse en este orden. Cada una comprobará sus dependencias, la configuración y el diccionario vigentes. Cancelá primero las que no quieras ejecutar.','Continuar envíos',async()=>{
      try{await api('orders/resume',{confirmation});notify('Cola habilitada; las órdenes siguen sus comprobaciones antes de enviarse.');}catch(e){notify(e.message);}finally{await refreshOrders();}
    });
  };
  function applyReport(data) {
    if(!data?.report?.lineas)return;
    diagnosticReport=validateReport(data.report);adminDetails=data.details||null;
    if(adminDetails)adminDetails=validatePrivate(adminDetails);
    lastReportRun=data.run_id;renderDiagnostic();
    $('#reportRunLink').href='https://github.com/SanLean17/parque-movil-ftr/actions'+(lastReportRun?'/runs/'+lastReportRun:'');
  }
  async function loadReport(runId) {
    if(!runId||checkedReports.has(runId))return;
    checkedReports.add(runId);
    try { const data=await api('report',{run_id:Number(runId)}); if(data?.operation?.message)notify(data.operation.message); applyReport(data); }
    catch(e) { checkedReports.delete(runId); notify(e.message); }
  }
  function showReadState(data) {
    if(data.oneoffs)publishedOneoffs=data.oneoffs;
    renderOneoffs();
    for(const key of ['drive','cnrt']) {
      const row=data.state?.[key]||{}, timing=data.schedule?.[key];
      $('#'+key+'Last').textContent=row.read_utc?localTime(row.read_utc):'Todavía sin lectura publicada por esta integración.';
      const labels={disabled:'DESACTIVADA',error:'REVISAR',overdue:'ACTUALIZACIÓN ATRASADA',pending:'PENDIENTE',saved:'DATOS GUARDADOS',waiting:'PROGRAMADA'};
      const current=timing?.status||(row.status==='error'?'error':row.read_utc?'saved':'waiting');
      const badge=$('#'+key+'CloudState');badge.textContent=labels[current]||'COMPROBAR ESTADO';
      badge.className='badge '+(current==='error'?'error':current==='saved'?'good':current==='disabled'?'':'wait');
      $('#'+key+'AgendaNote').textContent=timing ? timing.pending ?
        'Lectura pendiente desde '+localTime(timing.next_due_utc)+'. La última lectura de arriba todavía no se reemplazó.' :
        timing.next_due_utc?'Próximo horario recurrente: '+localTime(timing.next_due_utc)+'.':'La actualización automática está desactivada.' :
        'Último estado guardado en este equipo. Conectá GitHub para comprobar la agenda.';
      const note=$('#'+key+'AgendaNote'),health=data.schedule_health;
      const healthLabels={active:'Workflow activo; horario publicado comprobado.',disabled:'WORKFLOW DESHABILITADO. La programación no está completamente activa.',mismatch:'PROGRAMACIÓN INCONSISTENTE. Revisá la rama y los horarios publicados.',unknown:'Estado del workflow sin verificar. No se confirma que la programación esté activa.'};
      note.append(el('p',healthLabels[health?.status]||healthLabels.unknown,'small'));
      const event=health?.last_scheduled;
      if(event?.created_at)note.append(el('p','Último evento automático en GitHub: '+localTime(event.created_at)+'.','small'));
      const trace=(data.oneoffs?.execution_history||[]).filter(r=>r.source===key&&r.expected_utc).at(-1);
      if(trace) {
        const kinds={recovered:'RECUPERADA',delayed:'DEMORADA',scheduled:'PROGRAMADA'};
        note.append(el('p','Último turno: '+localTime(trace.expected_utc)+' · '+(kinds[trace.kind]||trace.kind)+' · '+(trace.status==='error'?'ERROR':trace.status==='running'?'En ejecución':'Lectura guardada')+'.','small'));
        if(trace.read_utc)note.append(el('p','Lectura real: '+localTime(trace.read_utc)+'.','small'));
        if(trace.error)note.append(el('p',trace.error,'small'));
      }
      if(['pending','error'].includes(data.state?.publication?.status))note.append(el('p','PUBLICACIÓN PENDIENTE: los datos guardados todavía no quedaron verificados en la web. GitHub reintentará publicarlos.','small'));
    }
  }
  async function refresh(reload=false) {
    if(refreshLock)return false;
    refreshLock=true; lastRefresh=Date.now();
    try {
      const data=await api('status');online=true;authorized=true;
      if(reload || remoteDigest===null || (!dirty&&!localDraft)) {
        remoteDigest=data.digest; if(reload||(!dirty&&!localDraft))fromRemote(data.config);
      }
      showReadState(data);remoteRuns=data.runs||[];
      if(data.outbox) {orders=data.outbox.orders;queueError=data.outbox.error;queueInfo=data.outbox;}
      showActivity();
      const latest=remoteRuns.find(r=>r.status==='completed');
      if(latest&&!['agenda_only','configuration','oneoff_saved','coalesced','publication'].includes(latest.effect))await loadReport(latest.id);
      const driveRun=Number(data.state?.drive?.run_id);
      if(driveRun&&(!lastReportRun||Date.parse(data.state.drive.read_utc||'1970-01-01')>Date.parse(diagnosticReport?.inicio_lectura_utc||'1970-01-01')))await loadReport(driveRun);
      if(data.digest!==remoteDigest)$('#savedState').textContent='La configuración de GitHub cambió. Recargala y revisá tu borrador antes de confirmar otra orden.';
      return true;
    } catch(e) {
      online=false;if(e.code==='authorization')authorized=false;queueError=e.message;showActivity();return false;
    } finally {refreshLock=false;locks();}
  }
  saveDraft=async function(message='Borrador guardado en este equipo. Todavía no se publicó.') {
    if(!collect())return false;
    try {await api('draft',{config:model(),expected:remoteDigest});localDraft=true;state.savedAt=new Date().toISOString();dirty=false;render();notify(message);return true;}
    catch(e) {notify(e.message);return false;}
  };
  async function submit(action) {
    if(submitting)return;
    if(!remoteDigest){notify('Primero consultá una vez la configuración de GitHub. Podés guardar el borrador sin conexión.');return;}
    if(['config','diagnostic'].includes(action)&&!collect())return;
    await refreshOrders();
    const parent=[...orders].reverse().find(r=>r.action==='config'&&['pending','authorization','sending','unknown','sent'].includes(r.status));
    if(action==='config'&&parent){notify('Ya hay una configuración confirmada. Esperá su resultado o cancelala antes de confirmar otra.');return;}
    const dependency=['drive','cnrt','all'].includes(action)&&parent?parent.id:null;
    const explanation=action==='config' ? 'Cambiar solamente horarios guarda la programación sin leer fuentes. Si cambiás planilla, período o líneas, se valida la fuente antes de publicarla. Una planilla válida y vacía deja el conteo en cero.' :
      action==='diagnostic' ? 'GitHub leerá la planilla del borrador y generará un informe, sin cambiar la fuente activa ni los CSV.' :
      dependency ? 'Primero debe publicarse la configuración que ya confirmaste. Después se ejecutará esta actualización con esa configuración. Los cambios posteriores del borrador no están incluidos.' :
      'Se ejecutará con la configuración publicada que consultó este equipo. Los cambios del borrador sin publicar no están incluidos.';
    // Copia inmutable de lo que el diálogo pide confirmar.
    const payload={action,config:structuredClone(model()),expected:remoteDigest,depends_on:dependency};
    openDialog(captions[action],explanation+' La orden quedará guardada como Pendiente de envío; se enviará cuando el programa esté abierto, autorizado y con Internet. Podés cancelarla antes del envío.','Confirmar orden',async()=>{
      if(submitting)return;submitting=true;locks();
      try {
        const data=await api('submit',payload);
        addEvent(captions[action]+': '+data.message);notify(data.message);await refreshOrders();showView('schedules');
      } catch(e) {notify(e.message);} finally {submitting=false;locks();}
    });
  }
  function baParts(value=new Date()) {
    return Object.fromEntries(new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Argentina/Buenos_Aires',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(value).filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));
  }
  function oneoffFields(key,row) {
    const p=baParts(new Date(row.at));$('#'+key+'OneoffDate').value=p.year+'-'+p.month+'-'+p.day;$('#'+key+'OneoffTime').value=p.hour+':'+p.minute;
  }
  function renderOneoffs() {
    for(const key of ['drive','cnrt']) {
      const box=$('#'+key+'OneoffStatus');if(!box)continue;box.replaceChildren();
      const row=publishedOneoffs?.pending?.[key];
      $('#'+key+'OneoffFields').hidden=!!row&&!editingOneoff[key];
      if(row) {
        box.append(el('strong','Actualización programada'),el('p',localTime(row.at)),el('p',online?'Guardada en GitHub. La PC puede estar apagada.':'Según la última consulta a GitHub. Actualizá el estado para comprobar cambios.','small'));
        const actions=el('div',undefined,'actions'),change=el('button','CAMBIAR','text-btn'),cancel=el('button','CANCELAR','text-btn');
        change.type=cancel.type='button';cancel.dataset.oneoffCancel=key;
        change.onclick=()=>{editingOneoff[key]=true;oneoffFields(key,row);renderOneoffs();$('#'+key+'OneoffDate').focus()};
        cancel.onclick=()=>submitOneoff(key,true);cancel.disabled=!remoteDigest||submitting;
        actions.append(change,cancel);box.append(actions);
      } else box.append(el('p',publishedOneoffs?'Sin actualización extraordinaria pendiente.':'Conectá GitHub para consultar la programación extraordinaria.','small'));
      for(const order of orders.filter(r=>r.oneoff?.source===key&&openStates.includes(r.status)))box.append(el('p',(order.label||'Pendiente de envío')+' · '+order.message,'small'));
      const history=(publishedOneoffs?.history||[]).filter(r=>r.source===key).slice(-5).reverse();
      if(history.length) {
        const detail=el('details',undefined,'repeat-item');detail.append(el('summary','Historial de actualizaciones programadas'));
        for(const item of history) {
          const run=remoteRuns.find(r=>String(r.id)===String(item.run_id));
          const labels={success:'Lectura guardada',error:'ERROR',cancelled:'Cancelada',replaced:'Reemplazada',running:run?.status==='completed'?'ERROR: resultado sin confirmar':'En ejecución'};
          detail.append(el('p','PROGRAMADA MANUALMENTE · '+localTime(item.at)+' · '+(labels[item.status]||'Revisar estado'),'small'));
          if(item.error)detail.append(el('p',item.error,'small'));
          if(item.run_id&&/^\d+$/.test(String(item.run_id))) {const link=el('a','Ver resultado y publicación','text-btn');link.href='https://github.com/SanLean17/parque-movil-ftr/actions/runs/'+item.run_id;link.target='_blank';link.rel='noopener noreferrer';detail.append(link);}
        }box.append(detail);
      }
    }
  }
  async function submitOneoff(key,cancel=false) {
    const error=$('#'+key+'OneoffError');error.hidden=true;
    if(!remoteDigest||!publishedOneoffs){error.textContent='Consultá una vez el estado de GitHub antes de programar.';error.hidden=false;return;}
    const row=publishedOneoffs.pending?.[key];
    const extra={source:key,expected_id:row?.id||null};
    if(!cancel) {
      extra.date=$('#'+key+'OneoffDate').value;extra.time=$('#'+key+'OneoffTime').value;
      const n=baParts(),now=n.year+'-'+n.month+'-'+n.day+'T'+n.hour+':'+n.minute+':'+n.second;
      if(!extra.date||!extra.time){error.textContent='Completá una fecha y un horario válidos.';error.hidden=false;return;}
      if(extra.date+'T'+extra.time+':00'<=now){error.textContent='La fecha y hora deben ser posteriores al momento actual.';error.hidden=false;return;}
    }
    const action=cancel?'oneoff-cancel':'oneoff-set';
    const description=cancel?'Se cancelará solamente esta actualización extraordinaria. No se leerán fuentes.':
      'Se programará una sola lectura de '+(key==='drive'?'Drive':'CNRT')+' para '+extra.date.split('-').reverse().join('/')+' a las '+extra.time+' hs de Buenos Aires. GitHub puede iniciar con demora.';
    openDialog(captions[action],description+' El calendario recurrente no cambia. La orden queda Pendiente de envío hasta publicarse en GitHub.','Confirmar orden',async()=>{
      if(submitting)return;submitting=true;locks();
      try {const data=await api('submit',{action,expected:remoteDigest,oneoff:extra});editingOneoff[key]=false;notify(data.message);await refreshOrders();}
      catch(e){error.textContent=e.message;error.hidden=false;}finally{submitting=false;locks();}
    });
  }
  for(const key of ['drive','cnrt']) {
    const section=el('section');section.setAttribute('aria-label','Actualización programada '+key);
    section.append(el('hr',undefined,'rule'),el('h3','ACTUALIZACIÓN PROGRAMADA'));
    const fields=el('div');fields.id=key+'OneoffFields';const form=el('div',undefined,'forms');
    for(const [suffix,label,type] of [['Date','Fecha','date'],['Time','Horario','time']]) {
      const field=el('div',undefined,'field'),caption=el('label',label),input=el('input');input.type=type;input.id=key+'Oneoff'+suffix;caption.htmlFor=input.id;input.setAttribute('aria-describedby',key+'OneoffError');field.append(caption,input);form.append(field);
    }
    const actions=el('div',undefined,'actions end'),button=el('button','PROGRAMAR ACTUALIZACIÓN','btn secondary');button.type='button';button.dataset.oneoffSubmit=key;button.onclick=()=>submitOneoff(key);actions.append(button);fields.append(form,actions);
    const error=el('p',undefined,'error');error.id=key+'OneoffError';error.setAttribute('role','alert');error.hidden=true;
    const status=el('div',undefined,'inline-note');status.id=key+'OneoffStatus';status.setAttribute('aria-live','polite');
    section.append(fields,error,el('p','Una sola vez, en horario de Buenos Aires. No cambia la frecuencia habitual.','small'),status);
    $('#'+key+'AgendaNote').after(section);
  }
  $$('[data-run]').forEach(b=>b.onclick=()=>submit(b.dataset.run));
  $('#previewSend').onclick=()=>submit('config');
  for(const id of ['sourceForm','schedulesForm'])$('#'+id).onsubmit=e=>{e.preventDefault();submit('config');};
  $('#testSheet').onclick=()=>submit('diagnostic');
  $('#refreshCloud').onclick=async()=>{await refreshOrders();await refresh();};
  $('#saveAll').onclick=()=>saveDraft();
  async function reloadConfig() {
    // Una consulta fallida conserva el borrador y los campos, incluso al estar sin Internet.
    const data=await api('status');await api('reset-draft',{});localDraft=false;dirty=false;
    remoteDigest=data.digest;fromRemote(data.config);showReadState(data);online=true;locks();
  }
  for(const id of ['resetDemo','reloadRemote'])$('#'+id).onclick=()=>openDialog('Recargar configuración publicada',
    'Reemplaza el borrador por la configuración de GitHub si se puede consultar. Conserva credenciales, informes, tema y órdenes confirmadas.','Recargar',async()=>{
      try {await reloadConfig();notify('Configuración publicada recuperada.');}catch(e){online=false;locks();notify(e.message);}
    });
  $('#themeToggle').onclick=async()=>{
    const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;
    try {localStorage.setItem(THEME,theme);await api('preferences',{theme});}catch(e){notify('El tema cambió, pero no se pudo guardar para el próximo inicio.');}
  };
  $('#connectionForm').onsubmit=async e=>{
    e.preventDefault();const input=$('#githubToken'),value=input.value;input.value='';$('#connectionError').hidden=true;
    try {const data=await api('connect',{token:value});authorized=true;notify(data.persistent?'GitHub conectado. Autorización protegida en Windows.':'GitHub conectado solo para esta sesión.');await refresh();showView('schedules');}
    catch(err){$('#connectionError').textContent=err.message;$('#connectionError').hidden=false;}
  };
  $('#disconnect').onclick=()=>openDialog('Desconectar este equipo','Elimina la autorización local. Conserva las órdenes pendientes. Los bots de GitHub siguen funcionando.','Desconectar',async()=>{
    try {await api('disconnect',{});online=false;authorized=false;locks();notify('Este equipo quedó desconectado.');}catch(e){notify(e.message);}
  });
  $('#quitPanel').onclick=()=>openDialog('Cerrar el programa',
    'Las órdenes todavía no enviadas esperan hasta que abras el programa. Los bots siguen funcionando en GitHub. Guardá primero los cambios del borrador.','Cerrar programa',async()=>{
      try {await api('quit',{});document.body.textContent='Panel cerrado. Podés cerrar esta pestaña.';}catch(e){notify(e.message);}
    });
  $('#importLegacy').onclick=()=>$('#legacyFile').click();
  $('#legacyFile').onchange=async e=>{
    const file=e.target.files[0];e.target.value='';if(!file)return;
    if(file.size>32*1024*1024){notify('El ZIP supera el límite de 32 MB.');return;}
    openDialog('Recuperar informes de 06.3','Se recuperan únicamente la llave y el informe del ZIP anterior, dentro de este equipo. No se ejecuta su programa, no se envía a Internet y se conserva un informe local más reciente.','Recuperar',async()=>{
      try {const form=new FormData();form.append('archive',file);const data=await api('import-legacy',form);applyReport(data.diagnostic);notify(data.message);}
      catch(err){notify(err.message);}
    });
  };
  try {
    const saved=await api('bootstrap');
    if(saved.preferences?.theme)document.documentElement.dataset.theme=saved.preferences.theme;
    if(saved.remote){remoteDigest=saved.remote.digest;fromRemote(saved.remote.config);showReadState(saved.remote);}
    if(saved.draft){localDraft=true;state={...initial(),...saved.draft.config,savedAt:saved.draft.saved_at};remoteDigest=saved.draft.expected||remoteDigest;dirty=false;populate();}
    applyReport(saved.diagnostic);authorized=saved.connected;await refreshOrders();
    if(authorized)await refresh();else locks();
  } catch(e) {notify(e.message);locks();}
  if(diagnosticReport.estado==='SIN_INFORME') {
    for(const id of ['diagTabs','diagLines','diagUnique','errorsTotal','warningsTotal','informationTotal'])$('#'+id).textContent='—';
    $('#diagTotals').textContent='Todavía no hay un informe en este equipo. Recuperá el de 06.3 en Conexiones o consultá los informes de GitHub.';
    $('#incidentList').replaceChildren(el('div','Todavía no se cargó un informe. Abrí Conexiones o Actualizaciones.','panel empty'));
  }
  showView('schedules');document.documentElement.dataset.ready='true';
  setInterval(async()=>{
    await refreshOrders();
    if(authorized && Date.now()-lastRefresh>(document.hidden?120000:60000))await refresh();
  },10000);
})();
