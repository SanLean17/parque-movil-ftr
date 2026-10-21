(function() {
  'use strict';
  let rows=[],ready=false,view='ALL',query='',generation=0,warning='';
  const open=new Set(),section=document.getElementById('historySection'),body=document.getElementById('historyTbody');
  function element(tag,text,classes){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(classes)e.className=classes;return e;}
  function filter(status,search) {view=status;query=String(search||'').trim().toUpperCase();render();}
  function render() {
    section.hidden=view!=='CONTROLADO'||!ready||!rows.length;
    if(section.hidden)return;
    body.replaceChildren();document.getElementById('historyNote').textContent=warning||'La ausencia en este parque no confirma una baja oficial.';
    const shown=rows.filter(r=>r.dominio.includes(query)||r.controles.some(c=>c.interno.includes(query)));
    if(!shown.length){const tr=element('tr'),td=element('td','No hay coincidencias para esta búsqueda.','py-4 px-2 text-center text-gray-500 dark:text-gray-400');td.colSpan=5;tr.append(td);body.append(tr);return;}
    for(const row of shown) {
      const tr=element('tr',undefined,'text-center divide-x divide-gray-200 dark:divide-gray-700 bg-gray-50 dark:bg-gray-800/70');
      tr.dataset.domain=row.dominio;
      for(const value of [row.dominio,row.internos.join(' / ')||'—',FTRHistory.displayDate(row.ultima_fiscalizacion),'FUERA DEL PARQUE ACTUAL'])tr.append(element('td',value,'py-2.5 px-2 font-code text-gray-600 dark:text-gray-300'));
      const td=element('td',undefined,'py-2.5 px-2'),button=element('button','VER DETALLE','text-blue-800 dark:text-blue-300 font-semibold text-[11px] underline underline-offset-2 whitespace-normal');button.type='button';button.style.minWidth='5em';
      const detailId='history-'+row.linea+'-'+row.dominio;
      button.setAttribute('aria-controls',detailId);button.setAttribute('aria-expanded',String(open.has(row.dominio)));td.append(button);tr.append(td);body.append(tr);
      const detail=element('tr');detail.id=detailId;detail.hidden=!open.has(row.dominio);
      const cell=element('td',undefined,'py-3 px-3 text-xs text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-900');cell.colSpan=5;
      const content=element('div',undefined,'space-y-2 break-words');FTRHistory.renderDetail(content,row,{publicOnly:true});cell.append(content);detail.append(cell);body.append(detail);
      button.onclick=()=>{if(open.has(row.dominio))open.delete(row.dominio);else open.add(row.dominio);detail.hidden=!open.has(row.dominio);button.setAttribute('aria-expanded',String(!detail.hidden));button.textContent=detail.hidden?'VER DETALLE':'CERRAR DETALLE';};
      if(!detail.hidden)button.textContent='CERRAR DETALLE';
    }
  }
  async function update(line,fleet,controls) {
    const run=++generation;ready=false;rows=[];warning='';render();
    try {
      const manifest=await FTRData.manifest();
      const stamp=async name=>{try{return (await (await FTRData.fetch(name)).text()).trim();}catch{return null;}};
      const [controlsRead,fleetRead]=await Promise.all([stamp('ultima_actualizacion_controlados.txt'),stamp('ultima_actualizacion_parque.txt')]);
      const options={period:manifest.period,controlsHash:manifest.files_sha256[`controlados/linea${line}.csv`],provenance:{source:`controlados/linea${line}.csv y parques/linea${line}.csv · período ${manifest.period||'publicado'}`,controlsRead,fleetRead}};
      const path=`historial/linea${line}.json`;
      if(manifest.files_sha256[path]) {
        try {options.history=await (await FTRData.fetch(path)).json();FTRHistory.outside(line,fleet,controls,options);options.provenance.source+=` · ${path} (controles disponibles de la misma lectura)`;}
        catch {delete options.history;warning='No se pudo verificar el historial adicional. Se muestran los registros del CSV publicado; controles anteriores: Información no disponible.';}
      }
      const result=FTRHistory.outside(line,fleet,controls,options);
      if(run!==generation)return;
      rows=result;ready=true;render();
    } catch {if(run===generation){ready=false;render();}}
  }
  window.FTRHistoryPublic={update,filter,clear:()=>{generation++;ready=false;rows=[];render();}};
})();
