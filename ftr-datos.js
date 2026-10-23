/* Una vista usa un único manifiesto; un CSV de otra versión nunca se cuenta. */
(function () {
  'use strict';
  const base = new URL('.', location.href);
  const fetchOriginal = window.fetch.bind(window);
  let manifestPromise;
  const files = new Map();
  async function manifest() {
    if (!manifestPromise) manifestPromise = fetchOriginal(new URL('ftr_publicacion.json', base), {cache:'no-store'})
      .then(async response => {
        if (!response.ok) throw Error('No se pudo verificar la versión publicada.');
        const value = await response.json();
        if (!value || !Array.isArray(value.lines) || !value.files_sha256) throw Error('Manifiesto no verificable.');
        if (typeof lineas !== 'undefined' && JSON.stringify(lineas) !== JSON.stringify(value.lines)) throw Error('La portada pertenece a otra configuración. Recargá la página.');
        return value;
      });
    return manifestPromise;
  }
  async function checkedFetch(input) {
    const url = new URL(input, base);
    if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) throw Error('Archivo fuera del proyecto.');
    const name = url.pathname.slice(base.pathname.length);
    const m = await manifest();
    const expected = m.files_sha256[name];
    if (!/^[a-f0-9]{64}$/.test(expected || '')) throw Error('Archivo fuera de la versión publicada.');
    const line = name.match(/^(?:parques|controlados)\/linea([0-9]+)\.csv$/);
    if (line && !m.lines.includes(Number(line[1]))) throw Error('Línea no habilitada.');
    if (!files.has(name)) files.set(name, (async () => {
      url.search = '?ftr_version=' + expected;
      const r = await fetchOriginal(url, {cache:'no-store'});
      if (!r.ok) throw Error('No se pudo descargar el archivo.');
      const bytes = await r.arrayBuffer();
      const actual = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2,'0')).join('');
      if (actual !== expected) throw Error('Publicación en transición. Recargá para obtener una versión completa.');
      return bytes;
    })());
    return new Response(await files.get(name), {status:200});
  }
  function formatUpdate(raw) {
    raw=String(raw || '').trim();
    if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(raw) || !Number.isFinite(Date.parse(raw))) return '-';
    const [year,month,day]=raw.slice(0,10).split('-').map(Number);
    const calendar=new Date(Date.UTC(year,month-1,day));
    if(calendar.getUTCFullYear()!==year || calendar.getUTCMonth()!==month-1 || calendar.getUTCDate()!==day || Number(raw.slice(11,13))>23) return '-';
    const parts=new Intl.DateTimeFormat('es-AR',{timeZone:'America/Argentina/Buenos_Aires',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(raw));
    const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
    return `${p.day}/${p.month}/${p.year} a las ${p.hour}:${p.minute} hs.`;
  }
  async function loadUpdates() {
    await Promise.all([['parque','fechaParque','parque móvil'],['controlados','fechaControlados','unidades controladas']].map(async([file,id,label])=>{
      let date='-';
      try { date=formatUpdate(await (await checkedFetch('ultima_actualizacion_'+file+'.txt')).text()); } catch (_) {}
      const node=document.getElementById(id);
      if(node) node.textContent='Última actualización de '+label+' realizada el '+date;
    }));
  }
  window.FTRData = {fetch:checkedFetch, manifest, formatUpdate, loadUpdates};
  if (typeof Papa === 'undefined') return; // Las estadísticas solo consultan JSON.
  const parse = Papa.parse.bind(Papa);
  Papa.parse = function (input, options) {
    if (!options?.download || typeof input !== 'string' || !/^(?:parques|controlados)\//.test(input)) return parse(input, options);
    checkedFetch(input).then(r => r.text()).then(text => parse(text, {...options, download:false}))
      .catch(error => options.error?.(error));
  };
})();
