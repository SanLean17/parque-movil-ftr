/* Extensión FTR 06.1. No cambia conteos ni escribe CSV o datos de Google. */
(function () {
  'use strict';
  const style = document.createElement('style');
  style.textContent = `#fleetTbody[data-view="ALL"] tr[data-status="PENDIENTE"]{background-color:#e7eef8}
  .dark #fleetTbody[data-view="ALL"] tr[data-status="PENDIENTE"]{background-color:#192c40}
  #fleetTbody[data-view="ALL"] tr[data-status="PENDIENTE"]:hover{background-color:#dce8f8}
  .dark #fleetTbody[data-view="ALL"] tr[data-status="PENDIENTE"]:hover{background-color:#223a52}`;
  document.head.append(style);
  const body = document.getElementById('fleetTbody');
  if (body) {
    body.dataset.view = 'ALL';
    const original = window.setFilter;
    window.setFilter = function (value) {
      body.dataset.view = value;
      if (typeof original === 'function') original(value);
    };
    // Cambia el orden real del documento: izquierda/arriba y también teclado.
    const controlledButton = document.querySelector('button[onclick="copyControlled()"]');
    const pendingButton = document.querySelector('button[onclick="copyMissing()"]');
    if (controlledButton && pendingButton && controlledButton.parentElement === pendingButton.parentElement) {
      pendingButton.parentElement.insertBefore(controlledButton, pendingButton);
    }
  }
  window.copyControlled = async function () {
    const rows = Array.from(document.querySelectorAll('#fleetTbody tr[data-status="CONTROLADO"]'));
    if (!rows.length) { alert('No hay unidades controladas en el parque mostrado.'); return; }
    const id = new URLSearchParams(location.search).get('id') || '22';
    const lines = rows.map(row => {
      const cells = row.querySelectorAll('td');
      return '• Int. '+cells[1].textContent.trim()+' ('+cells[0].textContent.trim()+') — '+cells[6].textContent.trim();
    });
    const text = '*LÍNEA '+id+' - CONTROLADOS ('+rows.length+' unidades):*\n'+lines.join('\n');
    try {
      await navigator.clipboard.writeText(text);
      // Mismo aviso nativo que Copiar pendientes, con el texto que se copió.
      alert('¡Copiado al portapapeles!\n\n'+text);
    } catch (_) {
      window.prompt('Copiá la lista de controlados:', text);
    }
  };
  function dateTime(raw) {
    const date = new Date(String(raw).trim());
    if (Number.isNaN(date.getTime())) return 'sin fecha disponible';
    const parts = Object.fromEntries(new Intl.DateTimeFormat('es-AR', {timeZone:'America/Argentina/Buenos_Aires', day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', hourCycle:'h23'}).formatToParts(date).map(p=>[p.type,p.value]));
    return `${parts.day}/${parts.month}/${parts.year} a las ${parts.hour}:${parts.minute} hs`;
  }
  if (typeof window.formatarFechaActualizacion === 'function') window.formatarFechaActualizacion = dateTime;
  for (const [id, file, text] of [
    ['fechaParque','ultima_actualizacion_parque.txt','Última actualización de parque móvil realizada el '],
    ['fechaControlados','ultima_actualizacion_controlados.txt','Última actualización de unidades controladas realizada el ']
  ]) {
    const element = document.getElementById(id);
    if (!element) continue;
    element.title = 'Inicio de la lectura del último resultado guardado correctamente. Las cargas posteriores pueden no estar incluidas.';
    fetch(file+'?v='+Date.now(), {cache:'no-store'})
      .then(r=>{if(!r.ok)throw Error();return r.text();})
      .then(s=>{element.textContent=text+dateTime(s);})
      .catch(()=>{element.textContent=text+'sin fecha disponible';});
  }
})();
