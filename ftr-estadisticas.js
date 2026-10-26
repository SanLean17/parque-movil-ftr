/* Vista de agregados validados. No consulta Google, CNRT ni informes privados. */
(function () {
  'use strict';
  const MONTHS = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'];
  const SHORT = ['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'];
  const STATES = ['fuera_de_servicio','observado','sin_novedad','estado_vacio','estado_otro'];
  const CATEGORIES = {direccion:'DIRECCIÓN', frenos:'SISTEMA DE FRENOS', suspension:'SUSPENSIÓN', transmision:'TRANSMISIÓN', neumaticos:'NEUMÁTICOS', electrico:'SISTEMA ELÉCTRICO', otras:'OTRAS'};
  const COMPONENTS = {
    direccion:{columna_direccion:'Columna de dirección',caja_direccion:'Caja de dirección',brazo_pitman:'Brazo Pitman',rotulas_direccion:'Rótulas de dirección',barra_larga:'Barra larga',barra_corta:'Barra corta',amortiguador_direccion:'Amortiguador de dirección',cruceta_direccion:'Cruceta de cardán de dirección',direccion_sin_componente:'Dirección — otro componente'},
    frenos:{frenos_delanteros:'Frenos delanteros',frenos_traseros:'Frenos traseros',flexibles_freno:'Flexibles de freno',pulmon_freno:'Pulmón de freno',tanque_aire:'Tanque de aire',valvula_descarga:'Válvula de descarga',freno_servicio:'Freno de servicio',freno_estacionamiento:'Freno de estacionamiento',freno_emergencia:'Freno de emergencia',bloqueo_frenos:'Sistema de frenos — bloqueo',freno_sin_ubicacion:'Frenos — sin componente precisado'},
    suspension:{amortiguadores:'Amortiguadores',bujes:'Bujes',pulmon_suspension:'Pulmón de suspensión',valvula_niveladora:'Válvula niveladora',barra_estabilizadora:'Barra estabilizadora',tensores:'Tensores',suspension_sin_componente:'Suspensión — sin componente precisado'},
    transmision:{cardan:'Cardán',crucetas:'Crucetas',diferencial:'Diferencial',transmision_sin_componente:'Transmisión, sin componente precisado'},
    neumaticos:{neumaticos_delanteros:'Neumáticos delanteros',neumaticos_traseros:'Neumáticos traseros',tuercas_rueda:'Tuercas',bulones_rueda:'Bulones',neumatico_sin_ubicacion:'Neumáticos — sin ubicación precisada'},
    electrico:{corte_corriente:'Corte de batería / corte de corriente',sonora_marcha_atras:'Señal sonora de marcha atrás',electrico_sin_componente:'Eléctrico — sin componente precisado'},
    otras:{perdida_aire_no_especificada:'Pérdida de aire sin componente indicado',perdida_no_especificada:'Pérdida sin sistema indicado',perdida_hidraulica:'Pérdida hidráulica sin componente indicado',observacion_administrativa:'Observación administrativa',sin_clasificar:'Menciones pendientes de interpretación'}
  };
  const LEGACY = {direccion:['barra_larga','barra_corta','direccion_sin_componente'],frenos:['frenos_delanteros','frenos_traseros','flexibles_freno','freno_sin_ubicacion'],suspension:['amortiguadores','bujes','suspension_sin_componente'],transmision:['cardan','crucetas','transmision_sin_componente'],otras:['sin_clasificar']};
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
  function validateIndex(index, manifest) {
    const bad=()=>{throw Error('No se pudo verificar el archivo anual.');};
    if (!index || index.version!==1 || !Array.isArray(index.periodos) || !index.periodos.length) bad();
    let previous=Infinity;
    for (const r of index.periodos) {
      if (!integer(r.periodo) || r.periodo<2000 || r.periodo>2100 || r.periodo>=previous || r.archivo!=='estadisticas/'+r.periodo+'.json' || ![1,2,3,4].includes(r.version) || ![1,2,3,4,5,6,7,8].includes(r.version_reglas) || !Array.isArray(r.lineas) || r.lineas.some((n,i)=>!integer(n)||!n||i>0&&n<=r.lineas[i-1]) || !/^[a-f0-9]{64}$/.test(r.sha256) || manifest.files_sha256[r.archivo]!==r.sha256 || !Number.isFinite(Date.parse(r.lectura_planilla_utc))) bad();
      previous=r.periodo;
    }
    return index;
  }
  function validate(data, reference) {
    const bad = () => {throw Error('Las estadísticas no corresponden a una versión completa del período.');};
    if (!data || ![1,2,3,4].includes(data.version) || data.version!==reference.version || data.periodo!==reference.periodo || !Array.isArray(data.lineas) || !Array.isArray(data.mensual) || !data.totales || !data.anomalias || !data.destacados || !Array.isArray(data.proporciones)) bad();
    if (JSON.stringify(data.lineas.map(r=>r.linea))!==JSON.stringify(reference.lineas) || data.lectura_planilla_utc!==reference.lectura_planilla_utc || !Number.isFinite(Date.parse(data.lectura_planilla_utc)) || !/^\d{4}-\d{2}-\d{2}$/.test(data.corte_fecha)) bad();
    if(data.version>=3 && (!data.interpretacion || !integer(data.interpretacion.revision) || !data.interpretacion.revision || !/^[a-f0-9]{64}$/.test(data.interpretacion.sha256) || !data.calidad || typeof data.calidad.parcial!=='boolean' || !integer(data.calidad.registros_excluidos) || data.calidad.parcial!==Boolean(data.calidad.registros_excluidos))) bad();
    const readDate=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Argentina/Buenos_Aires',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(data.lectura_planilla_utc));
    if (readDate!==data.corte_fecha) bad();
    const totals = {registros_validos:'registros_periodo',unidades_unicas_por_linea:'dominios_unicos',unidades_repetidas:'unidades_repetidas',registros_fuera_de_servicio:'fuera_de_servicio',registros_observados:'observado',registros_sin_novedad:'sin_novedad',registros_sin_estado:'estado_vacio',registros_otro_estado:'estado_otro'};
    for (const [key,field] of Object.entries(totals)) {
      if (!integer(data.totales[key]) || data.lineas.some(r=>!integer(r[field])) || data.lineas.reduce((s,r)=>s+r[field],0)!==data.totales[key]) bad();
    }
    for (const r of data.lineas) if (STATES.reduce((s,k)=>s+r[k],0)!==r.registros_periodo || r.unidades_repetidas>Math.min(r.dominios_unicos,r.registros_periodo-r.dominios_unicos)) bad();
    if (data.mensual.length!==12 || data.mensual.reduce((s,m)=>s+m.controles,0)!==data.totales.registros_validos) bad();
    const [cy,cm,cd]=data.corte_fecha.split('-').map(Number);
    for (const [i,m] of data.mensual.entries()) {
      const relative=data.periodo*12+m.mes-(cy*12+cm);
      const state=relative>0?'futuro':relative===0?'en_curso':'completo';
      if (m.mes!==i+1 || !integer(m.controles) || m.estado!==state || state==='futuro'&&m.controles) bad();
      if (data.version>=2 && (!integer(m.dias_con_fiscalizaciones) || m.dias_con_fiscalizaciones>Math.min(m.controles,new Date(data.periodo,m.mes,0).getDate(),state==='en_curso'?cd:31) || Boolean(m.dias_con_fiscalizaciones)!==Boolean(m.controles))) bad();
    }
    if (data.minimo_controles_proporcion!==20 || data.proporciones.length!==data.lineas.length || new Set(data.proporciones.map(r=>r.linea)).size!==data.lineas.length) bad();
    for (const r of data.proporciones) {
      const line=data.lineas.find(l=>l.linea===r.linea);
      if (!line || r.fuera_de_servicio!==line.fuera_de_servicio || r.controles!==line.registros_periodo || r.porcentaje!==(r.controles?Math.round(1000*r.fuera_de_servicio/r.controles)/10:null) || r.muestra_suficiente!==(r.controles>=20)) bad();
    }
    for (const k of ['fuera_de_servicio','observado','registros_periodo']) {
      const count=Math.max(0,...data.lineas.map(r=>r[k])),item=data.destacados[k];
      if (!item || item.cantidad!==count || JSON.stringify(item.lineas)!==JSON.stringify(count?data.lineas.filter(r=>r[k]===count).map(r=>r.linea):[])) bad();
    }
    const a=data.anomalias,catalogue=a.version_reglas===1?LEGACY:Object.fromEntries(Object.entries(COMPONENTS).map(([k,v])=>[k,Object.keys(v).filter(id=>(a.version_reglas>=4||id!=='amortiguador_direccion')&&(a.version_reglas>=5||!['cruceta_direccion','bloqueo_frenos'].includes(id))&&(a.version_reglas>=6||id!=='diferencial')&&(a.version_reglas>=8||k!=='otras'||id==='sin_clasificar'))]));
    if (![1,2,3,4,5,6,7,8].includes(a.version_reglas) || a.version_reglas!==reference.version_reglas || data.version===1&&a.version_reglas!==1 || !['pendiente','parcial','disponible'].includes(a.estado) || !Array.isArray(a.categorias) || JSON.stringify(a.categorias.map(c=>c.id))!==JSON.stringify(Object.keys(catalogue))) bad();
    const pending=a.estado==='pendiente',count=n=>pending?n===null:integer(n);
    if(a.version_reglas>=4){if(a.motor_revision!==({4:7,5:8,6:9,7:10,8:11}[a.version_reglas]))bad();const p=a.elementos_fisicos;if(!p||!['cantidad_confirmada','menciones_con_cantidad','menciones_sin_cantidad'].every(k=>count(p[k]))||!pending&&(p.menciones_con_cantidad+p.menciones_sin_cantidad!==a.identificadas||p.cantidad_confirmada<p.menciones_con_cantidad))bad();}
    if (!count(a.identificadas) || !count(a.sin_clasificar) || !a.cobertura || !['registros_validos','con_columna','con_texto','vacios','sin_columna'].every(k=>count(a.cobertura[k]))) bad();
    for (const cat of a.categorias) {
      if (!count(cat.cantidad) || !Array.isArray(cat.componentes) || JSON.stringify(cat.componentes.map(c=>c.id))!==JSON.stringify(catalogue[cat.id])) bad();
      for (const c of cat.componentes) if (!count(c.cantidad) || !c.estados || !STATES.every(k=>count(c.estados[k])) || !pending&&STATES.reduce((s,k)=>s+c.estados[k],0)!==c.cantidad) bad();
      if (!pending&&cat.componentes.reduce((s,c)=>s+c.cantidad,0)!==cat.cantidad) bad();
    }
    if (!pending && (a.cobertura.registros_validos!==data.totales.registros_validos || a.cobertura.con_columna+a.cobertura.sin_columna!==a.cobertura.registros_validos || a.cobertura.con_texto+a.cobertura.vacios!==a.cobertura.con_columna || a.identificadas!==a.categorias.flatMap(c=>c.componentes).filter(c=>c.id!=='sin_clasificar').reduce((s,c)=>s+c.cantidad,0) || a.sin_clasificar!==a.categorias.find(c=>c.id==='otras').componentes.find(c=>c.id==='sin_clasificar').cantidad || (a.estado==='parcial')!==Boolean(a.cobertura.sin_columna))) bad();
    if(data.version===4){const k=data.kit_sube;if(!k||k.version!==1||!['pendiente','parcial','disponible'].includes(k.estado)||!Array.isArray(k.lineas)||k.lineas.length!==data.lineas.length)bad();const pending=k.estado==='pendiente';
      for(const [i,r] of k.lineas.entries()){const l=data.lineas[i];if(r.linea!==l.linea||r.controles!==l.registros_periodo|| (pending?(r.incidencias!==null||r.con_novedades!==null):(!integer(r.incidencias)||!integer(r.con_novedades)||r.incidencias>r.con_novedades||r.con_novedades>r.controles)))bad();}
      if(pending?k.controles_con_incidencia!==null:(!integer(k.controles_con_incidencia)||k.controles_con_incidencia!==k.lineas.reduce((n,r)=>n+r.incidencias,0)||(k.estado==='parcial')!==k.lineas.some(r=>r.con_novedades<r.controles)))bad();
    }
    return data;
  }
  function orderComponents(rows,names){return [...rows].sort((a,b)=>(b.cantidad??-1)-(a.cantidad??-1)||(names[a.id]||a.id).localeCompare(names[b.id]||b.id,'es',{sensitivity:'base'}));}
  function monthText(month) {
    return MONTHS[month.mes-1]+(month.estado==='futuro'?' — POSTERIOR A LA ÚLTIMA LECTURA':' — '+format(month.controles)+' CONTROLES — '+(month.dias_con_fiscalizaciones==null?'DÍAS: NO DISPONIBLES EN ESTA VERSIÓN':format(month.dias_con_fiscalizaciones)+' DÍAS CON FISCALIZACIONES')+(month.estado==='en_curso'?' · MES EN CURSO':''));
  }
  if (typeof module!=='undefined'&&module.exports) module.exports={validate,validateIndex,monthText,orderComponents,COMPONENTS,LEGACY};

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
      const r=data[key], card=el('div','highlight '+(key==='fuera_de_servicio'?'red':key==='observado'?'orange':'green')),left=el('div'),right=el('div');left.append(el('h3','',label));
      left.append(el('p','winner',r.lineas.length?(r.lineas.length===1?'Línea ':'Líneas ')+r.lineas.join(' · '):'Sin casos registrados'));
      if(r.lineas.length>1)left.append(el('p','tie','Empate: misma cantidad en cada línea.'));
      right.append(el('p','count',format(r.cantidad)),el('p','unit',key==='registros_periodo'?'TOTAL DE CONTROLES':r.lineas.length>1?'CONTROLES POR LÍNEA':'CONTROLES'));card.append(left,right);return card;
    }));
  }
  function ratioRow(r, {interactive=false, detail}={}) {
    const row=el(interactive?'button':'div','ratio-row'),label=el('span','ratio-label'),track=el('span','track'),fill=el('span','fill');
    if(interactive)row.type='button';
    label.append(el('span','','Línea '+r.linea),el('span','ratio-value',r.porcentaje==null?'—':r.porcentaje.toLocaleString('es-AR',{minimumFractionDigits:1,maximumFractionDigits:1})+' %'));
    fill.style.setProperty('--width',(r.porcentaje||0)+'%');track.append(fill);row.append(label,track,el('span','ratio-detail',detail??(r.controles?format(r.fuera_de_servicio)+' fuera de servicio / '+format(r.controles)+' controles':'Sin controles registrados · proporción no definida')));return row;
  }
  function proportions(data) {
    const principal=data.proporciones.filter(r=>r.muestra_suficiente),small=data.proporciones.filter(r=>!r.muestra_suficiente);let expanded=false;
    function draw(){
      $('ratios').replaceChildren(...(expanded?principal:principal.slice(0,8)).map(r=>ratioRow(r)));
      if(!principal.length)$('ratios').append(el('p','empty','Todavía no hay líneas con la muestra mínima para este ranking.'));
      $('smallRatios').replaceChildren(...small.map(r=>ratioRow(r)));$('smallSamples').hidden=!expanded||!small.length;
      $('showLines').hidden=principal.length<=8&&!small.length;$('showLines').setAttribute('aria-expanded',String(expanded));
      $('showLines').textContent=expanded?'Mostrar menos':'Ver todas las líneas ('+data.proporciones.length+')';
    }
    $('showLines').onclick=()=>{expanded=!expanded;draw();};draw();
  }
  function componentCard(id, component, category) {
    const row=el('article','component'+(!component?' unavailable':component.cantidad===0?' empty-component':''));
    const heading=el('h4','component-name',COMPONENTS[category][id]);
    const amount=component?.cantidad;
    const value=el('div','component-total');value.append(el('strong','component-count',format(amount)),el('span','',id==='sin_clasificar'?'MENCIONES PENDIENTES':'MENCIONES REGISTRADAS'));
    row.append(heading,value);
    if (amount==null) {row.append(el('p','component-status','Sin análisis disponible.'));return row;}
    if (!amount) {row.append(el('p','component-status','Sin menciones registradas.'));return row;}
    const states=[
      ['red',component.estados.fuera_de_servicio,'Fuera de servicio'],
      ['orange',component.estados.observado,'Observados'],
      ['green',component.estados.sin_novedad,'Sin novedad'],
      ['neutral',component.estados.estado_vacio+component.estados.estado_otro,'Sin estado reconocido']
    ];
    const bar=el('div','state-bar'),legend=el('div','state-legend');
    bar.setAttribute('role','img');
    bar.setAttribute('aria-label',states.filter(([,n])=>n).map(([,n,label])=>label+': '+format(n)+' de '+format(amount)).join('; '));
    for (const [color,n,label] of states) {
      const percent=(100*n/amount).toLocaleString('es-AR',{maximumFractionDigits:1})+' %';
      if (n) {const part=el('span','state-segment '+color);part.style.setProperty('--share',(100*n/amount)+'%');part.title=label+': '+percent;bar.append(part);}
      if (color==='neutral'&&!n) continue;
      const item=el('p','state-item '+color);item.append(el('strong','',format(n)),el('span','',label),el('span','state-percent',percent));legend.append(item);
    }
    row.append(bar,legend);return row;
  }
  function mechanics(data) {
    const pending=data.estado==='pendiente';
    $('mechanicsStatus').textContent=pending?'Sin análisis disponible.':data.estado==='parcial'?'Análisis parcial.':'';
    $('mechanicsStatus').hidden=data.estado==='disponible';
    const max=Math.max(1,...data.categorias.map(c=>c.cantidad||0));
    const buttons=Object.entries(CATEGORIES).map(([id,name])=>{
      const cat=data.categorias.find(c=>c.id===id),unavailable=pending||!cat;
      const b=el('button','category'+(unavailable?' pending':'')),label=el('span','category-label'),track=el('div','track'),fill=el('div','fill');
      b.type='button';b.dataset.category=id;b.setAttribute('aria-pressed','false');b.setAttribute('aria-controls','componentPanel');
      label.append(el('span','',name),el('span','category-value',unavailable?'—':format(cat.cantidad)));
      fill.style.setProperty('--width',100*(cat?.cantidad||0)/max+'%');track.append(fill);
      b.append(label,track,el('span','category-unit',unavailable?'Sin análisis disponible':id==='otras'?'Menciones registradas':'Menciones identificadas'));
      b.addEventListener('click',()=>{
        for(const other of buttons)other.setAttribute('aria-pressed',String(other===b));
        $('componentTitle').textContent=name;
        $('components').replaceChildren(...orderComponents(Object.keys(COMPONENTS[id]).map(key=>cat?.componentes.find(c=>c.id===key)||{id:key,cantidad:null}),COMPONENTS[id]).map(c=>componentCard(c.id,c,id)));
        $('componentNote').textContent=id==='otras'?'Incluye observaciones genéricas identificadas y, por separado, menciones pendientes de interpretación.':data.version_reglas===1?'Catálogo histórico.':'';
      });
      return b;
    });
    $('categories').replaceChildren(...buttons);buttons[0].click();
  }
  function kit(data){
    const k=data?.kit_sube,ready=k&&k.estado!=='pendiente';$('kitTotal').textContent=ready?format(k.controles_con_incidencia):'—';
    $('kitStatus').textContent=!ready?'Dato no calculado para este período.':k.estado==='parcial'?'Cobertura parcial: faltan observaciones en algunos controles.':k.controles_con_incidencia===0?'Sin incidencias de KIT SUBE registradas en este período.':'';
    $('kitStatus').hidden=!$('kitStatus').textContent;
    $('kitLines').replaceChildren();$('kitDetail').textContent='';
    const toggle=$('showKitLines');toggle.hidden=true;toggle.onclick=null;toggle.setAttribute('aria-expanded','false');if(!ready)return;
    const rows=[...k.lineas].sort((a,b)=>b.incidencias-a.incidencias||a.linea-b.linea);
    const initial=rows.length<=5?rows:rows.filter(r=>r.incidencias>0).slice(0,5);let expanded=false,selected=null;
    function draw(){
      $('kitLines').replaceChildren();
      for(const r of expanded?rows:initial){
      const b=ratioRow({...r,porcentaje:r.controles?100*r.incidencias/r.controles:null},{interactive:true,detail:format(r.incidencias)+' incidencias KIT / '+format(r.controles)+' controles'+(r.controles?'':' · proporción no definida')});
      b.dataset.kitLine=r.linea;b.setAttribute('aria-pressed',String(selected===r.linea));b.setAttribute('aria-controls','kitDetail');
      const pct=b.querySelector('.ratio-value').textContent;
      b.onclick=()=>{selected=r.linea;for(const other of $('kitLines').children)other.setAttribute('aria-pressed',String(other===b));$('kitDetail').textContent='Línea '+r.linea+' · '+format(r.incidencias)+' controles con incidencia KIT de '+format(r.controles)+' controles válidos · '+pct+'.';};$('kitLines').append(b);
      }
      toggle.hidden=rows.length<=5;toggle.setAttribute('aria-expanded',String(expanded));toggle.textContent=expanded?'Mostrar menos':'Ver todas las líneas ('+rows.length+')';
    }
    toggle.onclick=()=>{expanded=!expanded;if(!expanded&&!initial.some(r=>r.linea===selected)){selected=null;$('kitDetail').textContent='';}draw();};draw();
  }
  function clearData() {
    kit(null);
    metrics(null);
    for(const id of ['months','highlights','ratios','smallRatios','categories','components'])$(id).replaceChildren();
    for(const id of ['monthSelection','mechanicsStatus','componentNote','footerPeriod'])$(id).textContent='';
    $('lastRead').textContent='—';$('lastRead').removeAttribute('datetime');
    $('componentTitle').textContent='SELECCIONÁ UNA CATEGORÍA';
    $('showLines').hidden=true;$('smallSamples').hidden=true;$('historicalNote').hidden=true;$('loadError').hidden=true;
    $('availability').classList.remove('error');
  }
  let generation=0,index,manifest;
  async function loadPeriod(year) {
    const request=++generation;clearData();$('statistics').dataset.status='loading';$('availability').textContent='Verificando período…';
    try {
      const reference=index.periodos.find(r=>r.periodo===Number(year));
      if (!reference) throw Error('Período no disponible.');
      const data=validate(await (await FTRData.fetch(reference.archivo)).json(),reference);
      if(request!==generation)return;
      $('lastRead').dateTime=data.lectura_planilla_utc;
      $('lastRead').textContent=new Intl.DateTimeFormat('es-AR',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'America/Argentina/Buenos_Aires'}).format(new Date(data.lectura_planilla_utc))+' · Argentina';
      $('footerPeriod').textContent='Período '+data.periodo;
      metrics(data.totales);months(data.mensual);highlights(data.destacados);proportions(data);mechanics(data.anomalias);kit(data);
      $('availability').textContent=data.calidad?.parcial?'Histórico parcial · registros válidos':'Estadísticas verificadas';
      $('historicalNote').hidden=data.periodo===manifest.period&&data.version>=2;
      $('historicalNote').textContent='Archivo del período '+data.periodo+', conservado con su fecha de lectura y reglas v'+data.anomalias.version_reglas+'. Los meses reflejan lo disponible hasta esa lectura.'+(data.version===1?' Esta versión histórica no guardó los días únicos con fiscalizaciones.':'');
      $('statistics').dataset.status='ready';
    } catch (_) {
      if(request!==generation)return;
      clearData();$('availability').textContent='Datos no disponibles';$('availability').classList.add('error');$('loadError').hidden=false;
      $('loadError').textContent='No se pudo verificar una versión completa del período seleccionado. Recargá en unos minutos si la publicación está en curso. No se mezclan cifras de otros años.';$('statistics').dataset.status='error';
    }
  }
  async function sourceDates() {
    return FTRData.loadUpdates();
  }
  clearData();
  sourceDates();
  (async()=>{
    try {
      manifest=await FTRData.manifest();
      index=validateIndex(await (await FTRData.fetch('estadisticas/indice.json')).json(),manifest);
      const select=$('periodSelect');
      select.replaceChildren(...index.periodos.map(r=>{const o=el('option','',r.periodo);o.value=r.periodo;return o;}));
      select.value=String(index.periodos.some(r=>r.periodo===manifest.period)?manifest.period:index.periodos[0].periodo);
      select.disabled=false;select.addEventListener('change',()=>loadPeriod(select.value));
      await loadPeriod(select.value);
    } catch (_) {
      clearData();$('statistics').dataset.status='error';$('availability').textContent='Períodos no disponibles';$('availability').classList.add('error');$('loadError').hidden=false;
      $('loadError').textContent='No se pudo verificar el archivo de períodos. Recargá para obtener una publicación completa.';
    }
  })();
})();
