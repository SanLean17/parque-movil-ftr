/* Conexión 06.3.1. Solo órdenes confirmadas, nunca borradores automáticos. */
(async function () {
  'use strict';
  const csrf = document.querySelector('meta[name="ftr-csrf"]').content;
  let remoteDigest = null, online = false, authorized = false, refreshLock = false;
  let submitting = false, localDraft = false, lastReportRun = null, remoteRuns = [], orders = [];
  let lastRefresh = 0, queueError = null;
  const checkedReports = new Set();
  const openStates = ['pending', 'authorization', 'sending', 'unknown', 'sent', 'conflict'];
  const captions = {config:'Guardar y publicar configuración', diagnostic:'Probar lectura sin publicar',
    drive:'Actualizar planilla anual FTR', cnrt:'Actualizar parque móvil', all:'Actualizar ambos procesos'};
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
    const visible=[...orders.filter(r=>openStates.includes(r.status)), ...orders.filter(r=>!openStates.includes(r.status)).slice(-4).reverse()];
    for (const row of visible) {
      const p=el('p'); p.dataset.orderId=row.id;
      p.append(el('strong', (captions[row.action]||row.action)+' · '+(row.label||row.message)));
      p.append(document.createElement('br'), el('span',localTime(row.created_at)+' · '+row.message,'small'));
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
    locks();
  }
  async function refreshOrders() {
    try { const data=await api('orders'); orders=data.orders; queueError=data.error; }
    catch(e) { queueError=e.message; }
    showActivity();
  }
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
    for(const key of ['drive','cnrt']) {
      const row=data.state?.[key]||{}, timing=data.schedule?.[key];
      $('#'+key+'Last').textContent=row.read_utc?localTime(row.read_utc):'Todavía sin lectura publicada por esta integración.';
      const labels={disabled:'DESACTIVADA',error:'REVISAR',overdue:'ATRASADA',pending:'PENDIENTE',saved:'DATOS GUARDADOS',waiting:'PROGRAMADA'};
      const current=timing?.status||(row.status==='error'?'error':row.read_utc?'saved':'waiting');
      const badge=$('#'+key+'CloudState');badge.textContent=labels[current]||'COMPROBAR ESTADO';
      badge.className='badge '+(current==='error'?'error':current==='saved'?'good':current==='disabled'?'':'wait');
      $('#'+key+'AgendaNote').textContent=timing ? timing.pending ?
        'Lectura pendiente desde '+localTime(timing.next_due_utc)+'. La última lectura de arriba todavía no se reemplazó.' :
        timing.next_due_utc?'Próximo horario guardado: '+localTime(timing.next_due_utc)+'.':'La actualización automática está desactivada.' :
        'Último estado guardado en este equipo. Conectá GitHub para comprobar la agenda.';
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
      if(data.outbox) {orders=data.outbox.orders;queueError=data.outbox.error;}
      showActivity();
      const latest=remoteRuns.find(r=>r.status==='completed');
      if(latest&&!['agenda_only','configuration'].includes(latest.effect))await loadReport(latest.id);
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
