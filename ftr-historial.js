/* Comparación por línea y dominio. Compartida por la web y Administración FTR. */
(function(root) {
  'use strict';
  const text=v=>String(v??'').trim();
  const key=v=>text(v).replace(/^\ufeff/,'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  function get(row,names) { const k=Object.keys(row||{}).find(k=>names.includes(key(k)));return k===undefined?'':text(row[k]); }
  function domain(v) {
    const s=text(v).replace(/[\s\-\u200b\ufeff]/g,'');
    if(!/^[\x00-\x7f]*$/.test(s))return '';
    const upper=s.toUpperCase();return /^(?:[A-Z]{3}[0-9]{3}|[A-Z]{2}[0-9]{3}[A-Z]{2})$/.test(upper)?upper:'';
  }
  function internal(v) {const s=text(v);return /^\d+(?:\.0+)?$/.test(s)?s.replace(/\.0+$/,'').replace(/^0+(?=\d)/,''):s.toUpperCase();}
  function date(v) {
    const s=text(v);let y,m,d,match=s.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[ T])/);
    if(match)[,y,m,d]=match;
    else {match=s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:$|[ T])/);if(!match)return null;[,d,m,y]=match;}
    const dt=new Date(Date.UTC(+y,+m-1,+d));
    if(dt.getUTCFullYear()!==+y||dt.getUTCMonth()!==+m-1||dt.getUTCDate()!==+d)return null;
    return `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
  }
  const displayDate=v=>date(v)?date(v).split('-').reverse().join('/'):'Información no disponible';
  function belongs(row,line) {const value=get(row,['linea']);return !value||value.split(/[,;/|]/).some(v=>/^\d+(?:\.0+)?$/.test(v.trim())&&Number(v.trim())===Number(line));}
  function controls(rows,line) {
    return rows.filter(r=>belongs(r,line)).map(r=>({dominio:domain(get(r,['dominio','patente','carroceria_dominio','dominio_vehiculo'])),
      interno:internal(get(r,['interno','numero_interno'])),fecha:date(get(r,['fecha','fechas','ultima_fiscalizacion','fecha_fiscalizacion','fecha_control','fecha_visita','fecha_inspeccion']))})).filter(r=>r.dominio);
  }
  function grouped(events) {const groups=new Map();for(const e of events){if(!groups.has(e.dominio))groups.set(e.dominio,[]);groups.get(e.dominio).push(e);}return groups;}
  function record(line,dominio,events,references,provenance,full) {
    const history=[...events].sort((a,b)=>(b.fecha||'').localeCompare(a.fecha||'')||a.interno.localeCompare(b.interno));
    const last=history[0]?.fecha||null;
    const internals=[...new Set(history.filter(e=>e.fecha===last).map(e=>e.interno).filter(Boolean))].sort();
    return {linea:Number(line),dominio,internos:internals,ultima_fiscalizacion:last,controles:history,
      referencias:references.filter(r=>internals.includes(r.interno)&&r.dominio!==dominio),procedencia:provenance,historial_completo:full};
  }
  function outside(line,fleetRows,controlRows,options={}) {
    if(!Array.isArray(fleetRows)||!Array.isArray(controlRows))throw Error('Información no disponible: no se pudo comparar el parque y los controles.');
    const fleet=controls(fleetRows,line),current=new Set(fleet.map(r=>r.dominio)),latest=controls(controlRows,line);
    let events=latest,full=false;
    if(options.history) {
      const h=options.history;
      if(h.version!==1||h.linea!==Number(line)||h.periodo!==options.period||h.controles_sha256!==options.controlsHash||!Array.isArray(h.controles))throw Error('El historial no corresponde a estos controles publicados.');
      const parsed=controls(h.controles,line),byDomain=grouped(parsed),known=grouped(latest);
      if(parsed.length!==h.controles.length||parsed.some(r=>!r.fecha||Number(r.fecha.slice(0,4))!==h.periodo||!known.has(r.dominio)||r.fecha>known.get(r.dominio).map(e=>e.fecha||'').sort().at(-1))||latest.some(r=>!byDomain.get(r.dominio)?.some(e=>e.fecha===r.fecha&&e.interno===r.interno)))throw Error('El historial no coincide con los registros publicados.');
      events=parsed;full=true;
    }
    const refs=[...new Map(fleet.filter(r=>r.interno).map(r=>[r.dominio+'|'+r.interno,{dominio:r.dominio,interno:r.interno}])).values()];
    return [...grouped(events)].filter(([d])=>!current.has(d)).map(([d,evs])=>record(line,d,evs,refs,options.provenance||{},full)).sort((a,b)=>a.dominio.localeCompare(b.dominio));
  }
  function fromReport(report,detail,line) {
    if(!detail||detail.version!==3||detail.periodo!==report.periodo||detail.revision_repositorio!==report.revision_repositorio||detail.detectado_utc!==report.inicio_lectura_utc||!Array.isArray(detail.incidencias))throw Error('Información no disponible. Abrí el detalle privado correspondiente a este informe.');
    const issues=detail.incidencias.filter(x=>x.codigo==='NO_EN_PARQUE'&&x.linea===Number(line));
    const events=controls(issues.map(x=>({linea:x.linea,dominio:x.dominio_ingresado,interno:x.interno,fecha:x.fecha_control})),line);
    const refs=[...new Map(issues.flatMap(x=>(x.candidatos_mismo_interno||[]).filter(c=>internal(c.interno)===internal(x.interno)&&domain(c.dominio)).map(c=>({dominio:domain(c.dominio),interno:internal(c.interno)}))).map(r=>[r.dominio+'|'+r.interno,r])).values()];
    const provenance={source:'Informe administrativo de la misma lectura',controlsRead:report.inicio_lectura_utc,
      fleetRead:report.fecha_parque_comparado_utc||issues.find(x=>x.referencia_parque?.fecha_lectura_utc)?.referencia_parque.fecha_lectura_utc,
      revision:report.revision_repositorio};
    const rows=[...grouped(events)].map(([d,evs])=>record(line,d,evs,refs,provenance,true)).sort((a,b)=>a.dominio.localeCompare(b.dominio));
    const expected=report.estadisticas?.find(x=>x.linea===Number(line))?.no_en_parque;
    if(!Number.isInteger(expected)||rows.length!==expected)throw Error('El detalle disponible no permite reconstruir este indicador. Información no disponible para esta lectura.');
    return rows;
  }
  function renderDetail(container,row) {
    const doc=container.ownerDocument;
    function item(label,value){const p=doc.createElement('p'),strong=doc.createElement('strong');strong.textContent=label+': ';p.append(strong,doc.createTextNode(value));container.append(p);}
    container.replaceChildren();
    item('DOMINIO FISCALIZADO',row.dominio);item('INTERNO REGISTRADO',row.internos.join(' / ')||'Información no disponible');
    item('LÍNEA',String(row.linea));item('ÚLTIMA FISCALIZACIÓN',displayDate(row.ultima_fiscalizacion));
    item('SITUACIÓN',`No figura en el parque comparado de la Línea ${row.linea}. Esto no confirma una baja oficial.`);
    for(const i of row.internos){const candidates=row.referencias.filter(r=>r.interno===i).map(r=>r.dominio);item('REFERENCIA ACTUAL DEL INTERNO '+i,candidates.join(', ')||'Información no disponible');}
    if(!row.internos.length)item('REFERENCIA ACTUAL DEL INTERNO','Información no disponible');
    item('OBSERVACIÓN',row.referencias.length?'El interno figura asociado a otro dominio en el parque comparado. Posible renovación o reasignación del interno. No se encuentra confirmada una relación de reemplazo.':'No hay una referencia suficiente para establecer una relación con otro vehículo.');
    item('HISTORIAL DE CONTROLES',row.historial_completo?'Registros disponibles de la lectura indicada.':'Solo los registros conservados en el CSV publicado. Controles anteriores: Información no disponible.');
    const list=doc.createElement('ul');
    for(const e of row.controles){const li=doc.createElement('li');li.textContent=displayDate(e.fecha)+' · Interno: '+(e.interno||'Información no disponible');list.append(li);}container.append(list);
    const time=v=>{const d=new Date(v||NaN);return Number.isNaN(d.getTime())?'Información no disponible':new Intl.DateTimeFormat('es-AR',{dateStyle:'short',timeStyle:'short',hourCycle:'h23',timeZone:'America/Argentina/Buenos_Aires'}).format(d)+' hs';};
    item('PROCEDENCIA',row.procedencia.source||'Controles FTR y parque publicados de esta línea');
    item('LECTURA DE LA PLANILLA',time(row.procedencia.controlsRead));item('DESCARGA DEL PARQUE COMPARADO',time(row.procedencia.fleetRead));
    item('PRIMERA AUSENCIA DOCUMENTADA','Información no disponible');item('FECHA OFICIAL DE BAJA O REEMPLAZO','Información no disponible');
  }
  const api={domain,internal,date,displayDate,controls,outside,fromReport,renderDetail};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.FTRHistory=api;
})(typeof window==='undefined'?globalThis:window);
