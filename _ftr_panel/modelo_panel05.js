/* Modelo puro del panel local: sin red, sin credenciales, sin escritura remota. */
(function(root){
'use strict';
const clean=v=>String(v??'').trim();
const integer=v=>Number.isInteger(v)&&v>=0;
function dateOnly(v){const s=clean(v);let m=s.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[ T])/);if(m)return `${m[3]}/${m[2]}/${m[1]}`;m=s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:$|\s)/);return m?`${m[1].padStart(2,'0')}/${m[2].padStart(2,'0')}/${m[3]}`:s||'Sin fecha válida';}
function internal(v){const s=clean(v);return /^\d+(?:\.0+)?$/.test(s)?String(Number(s)):s.toUpperCase();}
function candidates(x){if(!internal(x.interno))return[];const seen=new Set();return(x.candidatos_mismo_interno||[]).filter(c=>{const d=clean(c.dominio).toUpperCase();if(internal(c.interno)!==internal(x.interno)||!(/^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$/.test(d))||seen.has(d))return false;seen.add(d);return true;});}
function possibleSolution(x){const cs=candidates(x);if(cs.length===1)return `${clean(cs[0].dominio).toUpperCase()} (referencia del parque para el mismo interno). Verificar antes de corregir: el interno pudo haberse reasignado.`;if(cs.length>1)return `hay varias referencias para ese interno: ${cs.map(c=>clean(c.dominio).toUpperCase()).join(', ')}. No se puede elegir una con certeza; verificar con el registro original.`;return 'no hay una referencia suficiente en el parque para ese interno. Verificar el dominio con el registro original.';}
function incidentReference(x){
 const s=[`Línea ${x.linea??'sin identificar'} · Fecha ${dateOnly(x.fecha_control||x.fecha_ingresada)}`,`Dominio cargado en la planilla: ${clean(x.dominio_ingresado)||'sin dominio'}`,`Interno: ${clean(x.interno)||'sin interno'}`,`Pestaña: ${clean(x.pestana)||'sin identificar'} · Fila: ${x.fila??'—'} · Celda: ${clean(x.celda)||'—'}`];
 s.push(x.codigo==='DOMINIO_INVALIDO'?'El dominio no cumple con el formato admitido.':clean(x.mensaje)||'Revisar el registro indicado.');
 if(x.codigo==='DOMINIO_INVALIDO')s.push('Posible solución: '+possibleSolution(x));
 else if(x.codigo==='FECHA_INVALIDA'||x.codigo==='FECHA_FUTURA')s.push('Posible solución: verificar y completar la fecha real del control en la planilla.');
 else{const cs=candidates(x);if(cs.length)s.push('Referencia del mismo interno en el parque: '+cs.map(c=>clean(c.dominio).toUpperCase()).join(', ')+'. No confirma una corrección ni una baja.');}
 return s.join('\n');
}
function lineLeaders(rows,key){const available=(rows||[]).filter(r=>r.pestana_encontrada===true&&integer(r[key]));const count=Math.max(0,...available.map(r=>r[key]));return{cantidad:count,lineas:count?[...new Set(available.filter(r=>r[key]===count).map(r=>r.linea))].sort((a,b)=>a-b):[],disponible:available.length>0};}
function unitLeaders(report,detail){
 if(!detail||!Array.isArray(detail.repetidos))return{disponible:false,cantidad:0,unidades:[]};
 const all=detail.repetidos.filter(r=>integer(r.veces)&&r.veces>=2);
 if(!all.length){const total=report.totales_estadisticas?.unidades_unicas_por_linea;return{disponible:integer(total),cantidad:total>0?1:0,unidades:[],todos:total>0,total:total||0};}
 const count=Math.max(...all.map(x=>x.veces));
 const units=all.filter(x=>x.veces===count).map(x=>{const controls=[...(x.controles||[])].sort((a,b)=>clean(a.fecha).localeCompare(clean(b.fecha)));const latest=controls.length?controls[controls.length-1].fecha:'';return{linea:x.linea,dominio:x.dominio,internos:[...new Set(controls.filter(c=>c.fecha===latest).map(c=>clean(c.interno)).filter(Boolean))],cantidad:count};});
 return{disponible:true,cantidad:count,unidades:units,total:units.length};
}
function schedule(a){return a.enabled?`Se actualiza cada ${a.days} ${a.days===1?'día':'días'} a las ${a.time} h`:'Actualización automática pausada';}
const api={dateOnly,possibleSolution,incidentReference,lineLeaders,unitLeaders,schedule};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FTRPanelModel=api;
})(globalThis);
