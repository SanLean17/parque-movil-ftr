/* Respaldo optativo dentro del panel existente. Sin credenciales en el DOM. */
(function () {
  'use strict';
  const section=document.querySelector('[data-page="schedules"]');
  if(!section)return;
  const box=document.createElement('div');box.className='panel';box.id='localClockPanel';
  box.innerHTML='<div class="panel-head"><div><p class="eyebrow">GITHUB + ESTA COMPUTADORA</p><h2>Respaldo automático desde esta PC</h2><p>Envía a GitHub los turnos pendientes según los horarios publicados, sin pulsar Actualizar ahora.</p></div><span class="badge" id="localClockBadge">DESACTIVADO</span></div><div class="inline-note"><strong>Necesita esta PC encendida, sin suspensión, con Internet y el programa FTR abierto.</strong> No instala tareas ocultas ni usa otro servicio. Si cerrás el programa o apagás el equipo, solo queda la programación de GitHub, cuyo arranque todavía debe comprobarse.</div><p class="small">Al activarlo, también se solicitará un turno vencido que siga pendiente. No modifica la planilla, los horarios ni el parque publicado por sí mismo.</p><div class="actions"><button type="button" class="btn" id="localClockEnable">Activar respaldo de esta PC</button><button type="button" class="btn secondary" id="localClockDisable" disabled>Desactivar respaldo</button></div><p id="localClockMessage" role="status" aria-live="polite" class="small">Consultando el programa local…</p>';
  const form=section.querySelector('#schedulesForm');form.after(box);
  let locked=false;
  const enable=box.querySelector('#localClockEnable'),disable=box.querySelector('#localClockDisable');
  const csrfMatch=document.documentElement.innerHTML.match(/const csrf='([^']+)'/);
  if(!csrfMatch){box.querySelector('#localClockMessage').textContent='No se pudo iniciar este control. Volvé a abrir el programa.';return;}
  async function api(body){
    const options={method:body===undefined?'GET':'POST',headers:{'X-FTR-CSRF':csrfMatch[1]},cache:'no-store'};
    if(body!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
    const r=await fetch('/api/local-clock',options);const data=await r.json();
    if(!r.ok)throw Error(data.error||'No se pudo configurar el respaldo.');return data;
  }
  function render(data){
    const labels={off:'DESACTIVADO',waiting:'EN ESPERA',busy:'PROCESO EN GITHUB',sent:'SOLICITADO',awaiting:'ESPERANDO CONFIRMACIÓN',error:'REVISAR',other_instance:'OTRA VENTANA'};
    box.querySelector('#localClockBadge').textContent=!data.enabled?'DESACTIVADO':(labels[data.status]||'ACTIVADO');
    enable.disabled=locked||data.enabled;disable.disabled=locked||!data.enabled;
    let message=data.message||'';
    if(data.checked_at_utc)message+=' Última comprobación: '+new Intl.DateTimeFormat('es-AR',{hour:'2-digit',minute:'2-digit',second:'2-digit',timeZone:'America/Argentina/Buenos_Aires'}).format(new Date(data.checked_at_utc))+' hs.';
    box.querySelector('#localClockMessage').textContent=message;
  }
  async function change(value){
    if(locked)return;
    if(value&&!window.confirm('ACTIVAR RESPALDO AUTOMÁTICO DE ESTA PC\n\nMientras el programa esté abierto, esta PC solicitará automáticamente los turnos pendientes a GitHub, incluido el de hoy si está vencido. Debe permanecer encendida y con Internet. No cambia tus horarios ni instala tareas en Windows. ¿Activar?'))return;
    locked=true;enable.disabled=true;disable.disabled=true;
    try{const result=await api({enabled:value});locked=false;render(result);}
    catch(e){locked=false;box.querySelector('#localClockMessage').textContent=e.message;enable.disabled=false;disable.disabled=false;}
  }
  enable.addEventListener('click',()=>change(true));disable.addEventListener('click',()=>change(false));
  async function refresh(){if(locked)return;try{render(await api());}catch(e){box.querySelector('#localClockMessage').textContent=e.message;}}
  refresh();setInterval(refresh,15000);
})();
