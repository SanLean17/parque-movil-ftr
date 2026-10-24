const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
test('Componentes: cantidades descendentes, empates alfabéticos y ausencia distinta de cero',()=>{
  const {orderComponents}=require('../ftr-estadisticas.js');
  const rows=[{id:'z',cantidad:0},{id:'b',cantidad:4},{id:'u',cantidad:null},{id:'a',cantidad:4},{id:'c',cantidad:1}];
  const original=structuredClone(rows);
  assert.deepEqual(orderComponents(rows,{z:'Cero',b:'Buje',a:'Amortiguador',c:'Cardán',u:'Desconocido'}).map(x=>x.id),['a','b','c','z','u']);
  assert.deepEqual(rows,original);
});
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
// Ejecuta las funciones reales de la portada con respuestas CSV ficticias.
function run(fleet, controls, fail) {
  const elements = new Map();
  const context = {
    Date, Set, Math, String,
    document: {getElementById: id => {
      if (!elements.has(id)) elements.set(id, {textContent: ''});
      return elements.get(id);
    }},
    getProp: (row, keys) => keys.map(k => row[k]).find(v => v !== undefined) || '',
    parseFecha: () => new Date('2026-10-01T12:00:00Z'),
    formatFecha: value => value ? '01/10/2026' : 'Sin registros',
    Papa: {parse: (url, options) => {
      if ((fail === 'controls' && url.startsWith('controlados/')) || (fail === 'fleet' && url.startsWith('parques/'))) return options.error();
      options.complete({data: url.startsWith('parques/') ? fleet : controls, errors: []});
    }}
  };
  vm.createContext(context);
  const start = html.indexOf('    function cargarDatosLinea(');
  const end = html.indexOf('    function cargarFechas', start);
  // Incluye cargarDatosLinea y setFallbackControlados; corta antes de fechas.
  const candidate = html.slice(start, end > start ? end : html.indexOf('        fetch(', start));
  const fallbackEnd = candidate.indexOf("'Sin registros';");
  const fallbackErrorEnd = candidate.indexOf("'Lectura no disponible';");
  const last = Math.max(fallbackEnd > -1 ? fallbackEnd + "'Sin registros';".length : 0,
                        fallbackErrorEnd > -1 ? fallbackErrorEnd + "'Lectura no disponible';".length : 0);
  vm.runInContext(candidate.slice(0, candidate.indexOf('}', last) + 1), context);
  context.cargarDatosLinea(36);
  return Object.fromEntries([...elements].map(([id, node]) => [id, String(node.textContent)]));
}

test('portada compara dominios de la misma línea con su parque único', () => {
  const fleet = [{dominio:'AA111AA'}, {dominio:'AA111AA'}, {dominio:'BB222BB'}];
  const controls = [{linea:'36', dominio:'AA111AA'}, {linea:'36', dominio:'CC333CC'}, {linea:'37', dominio:'BB222BB'}];
  const result = run(fleet, controls);
  assert.equal(result['total-36'], '2');
  assert.equal(result['controladas-36'], '1');
  assert.equal(result['porcentaje-36'], '50%');
});
test('error de descarga no es cero controles', () => {
  const result = run([{dominio:'AA111AA'}], [], 'controls');
  assert.equal(result['controladas-36'], '—');
  assert.equal(result['porcentaje-36'], '—');
  assert.equal(result['visita-36'], 'Lectura no disponible');
});
test('tabla válida sin controles sí es cero', () => {
  const result = run([{dominio:'AA111AA'}], []);
  assert.equal(result['controladas-36'], '0');
  assert.equal(result['porcentaje-36'], '0%');
});


test('fechas de actualización argentinas: hora real, medianoche y errores', () => {
  const context={window:{fetch:()=>{}},location:{href:'https://ftr.test/'},document:{baseURI:'https://ftr.test/'},URL,Map,Date,Intl};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'..','ftr-datos.js'),'utf8'),context);
  const format=context.window.FTRData.formatUpdate;
  assert.equal(format('2026-10-23T01:31:10.527791+00:00'),'22/10/2026 a las 22:31 hs.');
  assert.equal(format('2026-10-23T03:00:00Z'),'23/10/2026 a las 00:00 hs.');
  assert.equal(format('2026-10-23T17:01:00-03:00'),'23/10/2026 a las 17:01 hs.');
  for(const raw of ['',null,'no disponible','2026-10-23','2026-10-23T12:00:00','2026-99-23T00:00:00Z'])assert.equal(format(raw),'-');
});
