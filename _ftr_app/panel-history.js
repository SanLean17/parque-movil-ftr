/* Detalle del indicador existente. Usa el mismo informe, sin consultar fuentes. */
(function() {
  const original=renderStatistics;
  const style=document.createElement('style');
  style.textContent='.fleet-table td.history-expand{display:table-cell;text-align:left;font-family:var(--font);font-weight:400;background:var(--surface-2);padding:16px 20px}.history-expand>div{width:100%}.history-expand p,.history-expand li{font-size:13px;line-height:1.5}.history-expand .history-data p{margin:8px 0}.history-expand li{margin-left:20px}.fleet-table td.history-expand:before{content:none}.fleet-table [data-history-line]{margin:4px auto 0;font-size:11px}@media(max-width:1000px){.fleet-table td.history-expand{display:block;width:100%}}';
  document.head.append(style);
  renderStatistics=function() {
    original();
    if(statisticsMode!=='cobertura')return;
    const reportRows=(diagnosticReport.estadisticas||[]).filter(x=>String(x.linea).includes($('#statisticsSearch').value.trim()));
    [...$('#statisticsRows').children].forEach((tr,index)=>{
      const row=reportRows[index],cell=tr.querySelector('[data-key="no_en_parque"]');
      if(!row||!cell||!Number.isInteger(row.no_en_parque)||row.no_en_parque<1)return;
      const button=el('button','VER DETALLE','text-btn');button.type='button';button.dataset.historyLine=row.linea;
      const id='statistics-history-'+row.linea;button.setAttribute('aria-controls',id);button.setAttribute('aria-expanded','false');cell.append(button);
      const expanded=el('tr'),td=el('td',undefined,'history-expand'),box=el('div');expanded.id=id;expanded.hidden=true;td.colSpan=tr.children.length;td.append(box);expanded.append(td);tr.after(expanded);
      button.onclick=()=>{
        expanded.hidden=!expanded.hidden;button.setAttribute('aria-expanded',String(!expanded.hidden));button.textContent=expanded.hidden?'VER DETALLE':'CERRAR DETALLE';
        if(expanded.hidden)return;
        box.replaceChildren();
        try {
          const records=FTRHistory.fromReport(diagnosticReport,adminDetails,row.linea);
          box.append(el('p','CONTROLADOS FUERA DEL PARQUE MÓVIL · LÍNEA '+row.linea));
          box.append(el('p','Comparación de este informe. Coincide con su indicador; una publicación posterior puede tener otro parque. Las ausencias no confirman bajas oficiales.','small'));
          for(const record of records){
            const item=el('details',undefined,'repeat-item');item.dataset.historyDomain=record.dominio;
            item.append(el('summary',record.dominio+' · Int. '+(record.internos.join(' / ')||'—')+' · '+FTRHistory.displayDate(record.ultima_fiscalizacion)+' · FUERA DEL PARQUE ACTUAL'));
            const data=el('div',undefined,'history-data');FTRHistory.renderDetail(data,record);item.append(data);box.append(item);
          }
        }catch(e){box.append(el('p',e.message,'small'));}
      };
    });
  };
  $('#statisticsSearch').oninput=renderStatistics;
  renderStatistics();
})();
