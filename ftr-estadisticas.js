/* Vista de agregados validados. No consulta Google, CNRT ni informes privados. */
(function () {
  'use strict';
  const MONTHS = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'];
  const SHORT = ['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'];
  const STATES = ['fuera_de_servicio','observado','sin_novedad','estado_vacio','estado_otro'];
  const CATEGORIES = {direccion:'DIRECCIÓN', frenos:'FRENOS', suspension:'SUSPENSIÓN', transmision:'TRANSMISIÓN', otras:'OTRAS / SIN CLASIFICAR'};
  const COMPONENTS = {
    direccion:{barra_larga:'Barra larga',barra_corta:'Barra corta',direccion_sin_componente:'Dirección, sin componente precisado'},
    frenos:{frenos_delanteros:'Frenos delanteros',frenos_traseros:'Frenos traseros',flexibles_freno:'Flexibles de freno',freno_sin_ubicacion:'Freno, sin ubicación precisada'},
    suspension:{amortiguadores:'Amortiguadores',bujes:'Bujes',suspension_sin_componente:'Suspensión, sin componente precisado'},
    transmision:{cardan:'Cardán',crucetas:'Crucetas',transmision_sin_componente:'Transmisión, sin componente precisado'},
    otras:{sin_clasificar:'Menciones pendientes de interpretación'}
  };
  const METRICS = [
    ['registros_validos','CONTROLES REGISTRADOS','Cada fiscalización válida.',''],
    ['unidades_unicas_por_linea','VEHÍCULOS ÚNICOS','Identidad: línea + dominio.',''],
    ['unidades_repetidas','VEHÍCULOS CONTROLADOS MÁS DE UNA VEZ','Cada vehículo cuenta una vez.',''],
    ['registros_fuera_de_servicio','FUERA DE SERVICIO','Resultado formal del control.','red'],
    ['registros_observados','OBSERVADOS','Resultado formal del control.','orange'],
    ['registros_sin_novedad','SIN NOVEDAD','Resultado formal del control.','green']
  ];
  const format = n => n == null ? '—' : Number(n).toLocaleString('es-AR');
  const integer = n => Number.isSafeInteger(n) && n >= 0;
  function validate(data, manifest) {
    const bad = () => {throw Error('Las estadísticas no corresponden a una versión completa del período.');};
    if (!data || data.version !== 1 || !integer(data.periodo) || data.periodo !== manifest.period || !Array.isArray(data.lineas) || !Array.isArray(data.mensual) || !data.totales || !data.anomalias || !data.destacados || !Array.isArray(data.proporciones)) bad();
    if (JSON.stringify(data.lineas.map(r=>r.linea)) !== JSON.stringify(manifest.lines) || !Number.isFinite(Date.parse(data.lectura_planilla_utc)) || !/^\d{4}-\d{2}-\d{2}$/.test(data.corte_fecha)) bad();
    const totals = {registros_validos:'registros_periodo',unidades_unicas_por_linea:'dominios_unicos',unidades_repetidas:'unidades_repetidas',registros_fuera_de_servicio:'fuera_de_servicio',registros_observados:'observado',registros_sin_novedad:'sin_novedad',registros_sin_estado:'estado_vacio',registros_otro_estado:'estado_otro'};
    for (const [key,field] of Object.entries(totals)) {
      if (!integer(data.totales[key]) || data.lineas.some(r=>!integer(r[field])) || data.lineas.reduce((s,r)=>s+r[field],0) !== data.totales[key]) bad();
    }
    for (const r of data.lineas) if (STATES.reduce((s,k)=>s+r[k],0)!==r.registros_periodo || r.unidades_repetidas>Math.min(r.dominios_unicos,r.registros_periodo-r.dominios_unicos)) bad();
    if (data.mensual.length!==12 || data.mensual.some((m,i)=>m.mes!==i+1 || !integer(m.controles) || !['futuro','en_curso','completo'].includes(m.estado) || m.estado==='futuro' && m.controles>0) || data.mensual.reduce((s,m)=>s+m.controles,0)!==data.totales.registros_validos) bad();
    if (data.minimo_controles_proporcion!==20 || data.proporciones.length!==data.lineas.length || new Set(data.proporciones.map(r=>r.linea)).size!==data.lineas.length) bad();
    for (const r of data.proporciones) {
      const line=data.lineas.find(l=>l.linea===r.linea);
      if (!line || r.fuera_de_servicio!==line.fuera_de_servicio || r.controles!==line.registros_periodo || r.porcentaje!==(r.controles?Math.round(1000*r.fuera_de_servicio/r.controles)/10:null) || r.muestra_suficiente!==(r.controles>=20)) bad();
    }
    for (const k of ['fuera_de_servicio','observado','registros_periodo']) {
      const count=Math.max(0,...data.lineas.map(r=>r[k]));const item=data.destacados[k];
      if (!item || item.cantidad!==count || JSON.stringify(item.lineas)!==JSON.stringify(count?data.lineas.filter(r=>r[k]===count).map(r=>r.linea):[])) bad();
    }
    const a=data.anomalias;
    if (a.version_reglas!==1 || !['pendiente','parcial','disponible'].includes(a.estado) || !Array.isArray(a.categorias) || JSON.stringify(a.categorias.map(c=>c.id))!==JSON.stringify(Object.keys(CATEGORIES))) bad();
    const pending=a.estado==='pendiente'; const count=n=>pending?n===null:integer(n);
    if (!count(a.identificadas) || !count(a.sin_clasificar) || !a.cobertura || !['registros_validos','con_columna','con_texto','vacios','sin_columna'].every(k=>count(a.cobertura[k]))) bad();
    for (const cat of a.categorias) {
      if (!count(cat.cantidad) || !Array.isArray(cat.componentes) || JSON.stringify(cat.componentes.map(c=>c.id))!==JSON.stringify(Object.keys(COMPONENTS[cat.id]))) bad();
      for (const c of cat.componentes) if (!count(c.cantidad) || !c.estados || !STATES.every(k=>count(c.estados[k])) || !pending && STATES.reduce((s,k)=>s+c.estados[k],0)!==c.cantidad) bad();
      if (!pending && cat.componentes.reduce((s,c)=>s+c.cantidad,0)!==cat.cantidad) bad();
    }
    if (!pending && (a.cobertura.registros_validos!==data.totales.registros_validos || a.cobertura.con_columna+a.cobertura.sin_columna!==a.cobertura.registros_validos || a.cobertura.con_texto+a.cobertura.vacios!==a.cobertura.con_columna || a.identificadas!==a.categorias.filter(c=>c.id!=='otras').reduce((s,c)=>s+c.cantidad,0) || a.sin_clasificar!==a.categorias[4].cantidad)) bad();
    return data;
  }
  function monthText(month) {
    return MONTHS[month.mes-1] + (month.estado==='futuro' ? ' — POSTERIOR A LA ÚLTIMA LECTURA' : ' — '+format(month.controles)+' CONTROLES'+(month.estado==='en_curso'?' · MES EN CURSO':''));
  }
  if (typeof module !== 'undefined' && module.exports) module.exports={validate,monthText,COMPONENTS};
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  function el(tag, cls, text) {const node=document.createElement(tag);if(cls)node.className=cls;if(text!=null)node.textContent=text;return node;}
  function theme() {
    const dark=document.documentElement.classList.contains('dark');
    $('themeIcon').className='fa-solid '+(dark?'fa-sun':'fa-moon');$('themeText').textContent=dark?'Claro':'Oscuro';
    $('themeButton').setAttribute('aria-label','Cambiar a modo '+(dark?'claro':'oscuro'));
  }
  $('themeButton').addEventListener('click',()=>{document.documentElement.classList.toggle('dark');try{localStorage.setItem('theme',document.documentElement.classList.contains('dark')?'dark':'light');}catch(_){}theme();});theme();
  function metrics(totals) {
    $('metrics').replaceChildren(...METRICS.map(([key,label,help,color])=>{const card=el('div','metric '+color);card.append(el('h3','metric-label',label),el('p','metric-value',format(totals?.[key])),el('p','metric-help',help));card.dataset.metric=key;return card;}));
    $('metrics').setAttribute('aria-busy',String(!totals));
  }
  function months(data) {
    const max=Math.max(1,...data.map(m=>m.controles));
    const buttons=data.map(m=>{const b=el('button','month'+(m.estado==='futuro'?' future':m.controles===0?' zero':''));b.type='button';b.setAttribute('aria-pressed','false');b.setAttribute('aria-label',monthText(m));b.dataset.month=m.mes;
      const well=el('span','bar-well');const bar=el('span','month-bar');bar.style.setProperty('--height',(100*m.controles/max)+'%');well.append(bar);
      b.append(el('span','month-number',m.estado==='futuro'?'—':format(m.controles)),well,el('span','month-label',SHORT[m.mes-1]));
      b.addEventListener('click',()=>{for(const other of buttons)other.setAttribute('aria-pressed',String(other===b));$('monthSelection').textContent=monthText(m);});return b;});
    $('months').replaceChildren(...buttons);
    const selected=data.find(m=>m.estado==='en_curso')||data.filter(m=>m.controles>0).at(-1);
    if(selected)buttons[selected.mes-1].click();
  }
  function highlights(data) {
    const labels={fuera_de_servicio:'LÍNEA CON MÁS FUERA DE SERVICIO',observado:'LÍNEA CON MÁS OBSERVADOS',registros_periodo:'LÍNEA CON MÁS CONTROLES REGISTRADOS'};
    $('highlights').replaceChildren(...Object.entries(labels).map(([key,label])=>{
      const r=data[key], card=el('div','highlight'),left=el('div'),right=el('div');left.append(el('h3','',label));
      left.append(el('p','winner',r.lineas.length?(r.lineas.length===1?'Línea ':'Líneas ')+r.lineas.join(' · '):'Sin casos registrados'));
      if(r.lineas.length>1)left.append(el('p','tie','Empate: misma cantidad en cada línea.'));
      right.append(el('p','count',format(r.cantidad)),el('p','unit',r.lineas.length>1?'controles por línea':'controles'));card.append(left,right);return card;
    }));
  }
  function ratioRow(r) {
    const row=el('div','ratio-row'),label=el('div','ratio-label'),track=el('div','track'),fill=el('div','fill');
    label.append(el('span','','Línea '+r.linea),el('span','ratio-value',r.porcentaje==null?'—':r.porcentaje.toLocaleString('es-AR',{minimumFractionDigits:1,maximumFractionDigits:1})+' %'));
    fill.style.setProperty('--width',(r.porcentaje||0)+'%');track.append(fill);row.append(label,track,el('p','ratio-detail',r.controles?format(r.fuera_de_servicio)+' fuera de servicio / '+format(r.controles)+' controles':'Sin controles registrados · proporción no definida'));return row;
  }
  function proportions(data) {
    const principal=data.proporciones.filter(r=>r.muestra_suficiente),small=data.proporciones.filter(r=>!r.muestra_suficiente);let expanded=false;
    $('minimum').textContent=data.minimo_controles_proporcion;
    function draw(){
      $('ratios').replaceChildren(...(expanded?principal:principal.slice(0,8)).map(ratioRow));
      if(!principal.length)$('ratios').append(el('p','empty','Todavía no hay líneas con la muestra mínima para este ranking.'));
      $('smallRatios').replaceChildren(...small.map(ratioRow));$('smallSamples').hidden=!expanded||!small.length;
      $('showLines').hidden=principal.length<=8&&!small.length;$('showLines').setAttribute('aria-expanded',String(expanded));
      $('showLines').textContent=expanded?'Mostrar menos':'Ver todas las líneas ('+data.proporciones.length+')';
    }
    $('showLines').onclick=()=>{expanded=!expanded;draw();};draw();
  }
  function mechanics(data) {
    const pending=data.estado==='pendiente';
    $('mechanicsStatus').textContent=pending?'Pendiente de la próxima lectura automática válida con NOVEDADES. Los indicadores del período ya están disponibles.':format(data.identificadas)+' anomalías identificadas · '+format(data.sin_clasificar)+' menciones sin clasificar.';
    $('mechanicsCoverage').textContent=pending?'Los informes anteriores no conservaron NOVEDADES para este análisis. No se asignan cantidades hasta leerlas.':
      'Cobertura: '+format(data.cobertura.con_columna)+' de '+format(data.cobertura.registros_validos)+' controles con columna reconocida · '+format(data.cobertura.con_texto)+' con texto · '+format(data.cobertura.vacios)+' celdas vacías.'+(data.cobertura.sin_columna?' Análisis parcial: '+format(data.cobertura.sin_columna)+' controles sin columna identificable.':'');
    const max=Math.max(1,...data.categorias.map(c=>c.cantidad||0));
    const buttons=data.categorias.map(cat=>{
      const b=el('button','category'+(pending?' pending':'')),label=el('span','category-label'),track=el('div','track'),fill=el('div','fill');b.type='button';b.dataset.category=cat.id;b.setAttribute('aria-pressed','false');b.setAttribute('aria-controls','componentPanel');
      label.append(el('span','',CATEGORIES[cat.id]),el('span','category-value',pending?'Pendiente':format(cat.cantidad)));fill.style.setProperty('--width',100*(cat.cantidad||0)/max+'%');track.append(fill);b.append(label,track);
      b.addEventListener('click',()=>{for(const other of buttons)other.setAttribute('aria-pressed',String(other===b));$('componentTitle').textContent=CATEGORIES[cat.id];
        $('components').replaceChildren(...cat.componentes.map(c=>{const row=el('div','component'),head=el('div','component-label');head.append(el('span','',COMPONENTS[cat.id][c.id]),el('span','component-count',format(c.cantidad)));row.append(head);
          if(!pending)row.append(el('p','component-states','Fuera de servicio: '+format(c.estados.fuera_de_servicio)+' · Observado: '+format(c.estados.observado)+' · Sin novedad: '+format(c.estados.sin_novedad)+(c.estados.estado_vacio+c.estados.estado_otro?' · Sin estado reconocido: '+format(c.estados.estado_vacio+c.estados.estado_otro):'')));return row;}));
        $('componentNote').textContent=cat.id==='otras'?'Son menciones pendientes de interpretación, no anomalías mecánicas confirmadas. Los textos originales no se publican.':pending?'Componentes preparados para la próxima lectura.':'Se cuentan menciones identificables de componentes y ubicaciones; no vehículos. La separación por resultado usa únicamente ESTADO.';
      });return b;
    });$('categories').replaceChildren(...buttons);buttons[0].click();
  }
  metrics(null);
  async function load() {
    try {
      const manifest=await FTRData.manifest();$('period').textContent=manifest.period;
      const data=validate(await (await FTRData.fetch('estadisticas_ftr.json')).json(),manifest);
      $('lastRead').dateTime=data.lectura_planilla_utc;
      $('lastRead').textContent=new Intl.DateTimeFormat('es-AR',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'America/Argentina/Buenos_Aires'}).format(new Date(data.lectura_planilla_utc))+' · Argentina';
      $('footerPeriod').textContent='© '+data.periodo;metrics(data.totales);months(data.mensual);highlights(data.destacados);proportions(data);mechanics(data.anomalias);
      const missing=data.totales.registros_sin_estado,other=data.totales.registros_otro_estado;
      $('unknownStates').textContent=missing+other?format(missing)+' controles sin ESTADO y '+format(other)+' con otro valor: incluidos en el total, sin asignarlos a un resultado.':'Todos los controles tienen un resultado formal reconocido.';
      $('availability').textContent=data.anomalias.estado==='pendiente'?'Indicadores verificados · NOVEDADES pendientes':data.anomalias.estado==='parcial'?'Indicadores verificados · análisis mecánico parcial':'Estadísticas verificadas';
      $('statistics').dataset.status='ready';
    } catch (_) {
      $('availability').textContent='Datos no disponibles';$('availability').classList.add('error');$('loadError').hidden=false;
      $('loadError').textContent='No se pudo verificar una versión completa de las estadísticas. Si la publicación está en curso, recargá en unos minutos. No se muestran cifras parciales.';$('statistics').dataset.status='error';
    }
  }
  load();
})();
