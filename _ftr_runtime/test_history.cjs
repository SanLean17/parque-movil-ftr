const {test}=require('node:test');
const assert=require('node:assert/strict');
const H=require('../ftr-historial.js');
const fleet=[{linea:154,dominio:'AA111AA',interno:'95'},{linea:154,dominio:'BB222BB',interno:'96'}];
const event=(dominio='CC333CC',interno='95',fecha='20/01/2026',linea=154)=>({linea,dominio,interno,fecha});
test('actuales e históricos simultáneos sin modificar datos ni contar el mismo interno como identidad',()=>{
 const controls=[event('AA111AA'),event()];const before=JSON.stringify([fleet,controls]);
 const rows=H.outside(154,fleet,controls);
 assert.equal(rows.length,1);assert.equal(rows[0].dominio,'CC333CC');assert.deepEqual(rows[0].referencias,[{dominio:'AA111AA',interno:'95'}]);
 assert.equal(JSON.stringify([fleet,controls]),before);
});
test('sin históricos: lista vacía',()=>assert.deepEqual(H.outside(154,fleet,[event('AA111AA')]),[]));
test('un parque válido vacío conserva todos los controles fuera de él',()=>assert.equal(H.outside(154,[],[event(),event('DD444DD')]).length,2));
test('parque o controles ausentes nunca equivalen a vacío válido',()=>{assert.throws(()=>H.outside(154,null,[]));assert.throws(()=>H.outside(154,[],null));});
test('vehículo que regresa al parque desaparece de fuera sin alterar historial',()=>{
 const controls=[event(),event('CC333CC','88','20/03/2026')];
 assert.equal(H.outside(154,fleet,controls)[0].controles.length,2);
 assert.equal(H.outside(154,[...fleet,{linea:154,dominio:'CC333CC',interno:99}],controls).length,0);
 assert.equal(controls.length,2);
});
test('la comparación respeta línea y dominio, incluso con códigos alfanuméricos',()=>{
 const controls=[event(),event('EE555EE','95','20/01/2026',155)];
 assert.equal(H.outside(154,[{linea:155,dominio:'CC333CC',interno:95},{linea:'154OP1',dominio:'CC333CC',interno:95}],controls).length,1);
 assert.equal(H.outside(154,[{linea:'154,2077IE',dominio:'CC333CC',interno:95}],controls).length,0);
});
test('repetidos: una unidad con todos los controles y última fecha real',()=>{
 const rows=H.outside(154,[],[event('CC333CC','94','20/03/2026'),event(),event('CC333CC','94','20/03/2026')]);
 assert.equal(rows.length,1);assert.equal(rows[0].controles.length,3);assert.equal(rows[0].ultima_fiscalizacion,'2026-03-20');assert.deepEqual(rows[0].internos,['94']);
});
test('mismo día y distintos internos: conservar ambas referencias sin elegir una',()=>{
 const rows=H.outside(154,fleet,[event(),event('CC333CC','96')]);assert.deepEqual(rows[0].internos,['95','96']);assert.equal(rows[0].referencias.length,2);
});
test('datos incompletos y fechas imposibles no inventan información',()=>{
 const row=H.outside(154,fleet,[event('CC333CC','','31/02/2026')])[0];
 assert.equal(row.ultima_fiscalizacion,null);assert.deepEqual(row.internos,[]);assert.deepEqual(row.referencias,[]);assert.equal(H.displayDate(null),'Información no disponible');
});
test('dominios inválidos conservan Ñ como diferencia: no se confunden con N',()=>{
 assert.equal(H.domain('AA111AÑ'),'');assert.equal(H.domain('AA111AN'),'AA111AN');assert.equal(H.domain('ßA111A'),'');
 assert.equal(H.domain('aa-111-aa'),'AA111AA');
});
test('referencias múltiples del mismo interno son referencias, deduplicadas y sin cruces de línea',()=>{
 const rows=H.outside(154,[...fleet,{linea:154,dominio:'EE555EE',interno:'095'},{linea:154,dominio:'EE555EE',interno:95},{linea:155,dominio:'FF666FF',interno:95}],[event()]);
 assert.deepEqual(rows[0].referencias.map(r=>r.dominio),['AA111AA','EE555EE']);
});
const archive=()=>({version:1,linea:154,periodo:2026,controles_sha256:'a'.repeat(64),controles:[event('CC333CC','88','01/01/2026'),event()]});
const options=()=>({period:2026,controlsHash:'a'.repeat(64),history:archive()});
test('historial adicional verificado amplía controles sin alterar unidades',()=>{
 const row=H.outside(154,fleet,[event()],options())[0];assert.equal(row.controles.length,2);assert.equal(row.historial_completo,true);assert.equal(row.ultima_fiscalizacion,'2026-01-20');
});
test('historial de otra versión, año o línea se rechaza',()=>{
 for(const change of [{periodo:2027},{linea:155},{controles_sha256:'b'.repeat(64)}])assert.throws(()=>H.outside(154,fleet,[event()],{...options(),history:{...archive(),...change}}));
});
test('un historial adicional no puede agregar dominios o perder el último control publicado',()=>{
 for(const controls of [[event('DD444DD')],[event('CC333CC','89')],[event('CC333CC','95','31/02/2026')],[event(),event('CC333CC','95','01/02/2026')],[event(),event('CC333CC','95','01/01/2025')]])assert.throws(()=>H.outside(154,fleet,[event()],{...options(),history:{...archive(),controles:controls}}));
});
const report={periodo:2026,revision_repositorio:'revision',inicio_lectura_utc:'2026-10-20T20:00:00Z',estadisticas:[{linea:154,no_en_parque:1}]};
const detail={version:3,periodo:2026,revision_repositorio:'revision',detectado_utc:report.inicio_lectura_utc,incidencias:[{codigo:'NO_EN_PARQUE',linea:154,dominio_ingresado:'CC333CC',interno:'95',fecha_control:'2026-01-20',candidatos_mismo_interno:[{dominio:'AA111AA',interno:'95'}]}]};
test('administración y web dan los mismos vehículos, fechas e internos para la misma comparación',()=>{
 const pick=row=>({dominio:row.dominio,linea:row.linea,internos:row.internos,fecha:row.ultima_fiscalizacion,referencias:row.referencias});
 assert.deepEqual(H.fromReport(report,detail,154).map(pick),H.outside(154,fleet,[event()]).map(pick));
});
test('un informe privado ausente, desfasado o inconsistente no inventa el indicador',()=>{
 assert.throws(()=>H.fromReport(report,null,154));assert.throws(()=>H.fromReport(report,{...detail,periodo:2027},154));
 assert.throws(()=>H.fromReport({...report,estadisticas:[{linea:154,no_en_parque:2}]},detail,154));
});
test('reemplazo de nueve vehículos deja cobertura nueva en cero y nueve históricos',()=>{
 const old=Array.from({length:9},(_,i)=>event('AB'+String(i).padStart(3,'0')+'CD',String(i)));
 const before=old.map(c=>({...c}));const after=old.map((c,i)=>({...c,dominio:'EF'+String(i).padStart(3,'0')+'GH'}));
 assert.equal(H.outside(154,before,old).length,0);assert.equal(H.outside(154,after,old).length,9);
 assert.equal(after.filter(r=>old.some(c=>c.dominio===r.dominio)).length,0);assert.equal(after.length,9);
});
