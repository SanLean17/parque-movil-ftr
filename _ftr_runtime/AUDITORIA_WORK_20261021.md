# Auditoría y reparación FTR — 21 de octubre de 2026

## Alcance y referencia

Repositorio exclusivo: `SanLean17/parque-movil-ftr`. Base inicial comprobada: `1824da51985b54fd91b74f580fc35aa1f5922dbb`, rama predeterminada `main`. Lectura y escritura confirmadas creando `ftr/auditoria-work-20261021` desde ese SHA. No se modifican configuración del usuario, CSV reales, sellos de lectura, secretos, DNS ni otros repositorios. No se dispara una lectura manual de producción.

Se inventariaron **200 archivos** de esa base frente a **147** del respaldo `69088bd844df11865cf5f5790dd18e13b251674e`, existente en `respaldo/antes-panel-06`. El respaldo fue generado por la actualización automática del 19/10 a las 08:32:02 UTC. [Inventario por archivo, función y dependencias](INVENTARIO_WORK_20261021.md).

Revisión detallada: workflows activos, contrato del servidor y puente 06.3, coordinación, agenda, calendario nativo, separación CNRT, lector anual, diagnóstico, generación/consumo web y pruebas. Revisión estructural: los 35 Python iniciales y los 130 CSV iniciales (48 parques, 48 controlados, 34 exportaciones CNRT históricas), sin columnas desalineadas. La revisión no certifica la verdad material de cada fiscalización, ni constituye una auditoría exhaustiva de seguridad de librerías o del ejecutable instalado. No se dispone en el repositorio de su `panel.html` final ni del binario 06.3; se comprueba el contrato mediante el código y pruebas, sin producir otro ejecutable.

`_ftr_pruebas/planilla_anual.py` **es producción**: lo importa el diagnóstico que usa `worker.google_snapshot`. `scraper.py` y `actualizar_parques.py` se ejecutan en un directorio temporal con configuración generada. Los CSV `cnrt/` del repositorio no alimentan ese directorio. El lector anterior de carpeta Drive, `control_actualizacion.py`, `${GITHUB_OUTPUT}`, la captura CNRT y las fechas antiguas se conservan como legado fuera del recorrido activo. `main064.py` y `local_clock*` no son dependencias de la automatización GitHub ni se activan.

## Evidencia de eventos: casos A–F

| Caso | Evidencia y conclusión |
|---|---|
| A. No apareció un evento | La API devolvió 50 ejecuciones `schedule` históricas; las cinco más recientes eran la del 21/10 y cuatro del 20/10. No proporciona evidencia del motivo de los eventos ausentes. No se atribuye a saturación, permisos o caché. |
| B. Espera/cancelación | [39351534215](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39351534215) fue creado 20/10 01:06:07 UTC y empezó 01:37:55 UTC: 31 min 48 s en espera; fue `push`, no `schedule`. Se observan también despliegues Pages cancelados junto a otro exitoso para el mismo commit; eso no prueba una lectura cancelada. |
| C. Arrancó y no leyó | [39567554012](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39567554012), `schedule`, 21/10 08:12:40 UTC / 05:12:40 Argentina: agenda exitosa, procesamiento y publicación omitidos. El log dice expresamente que no correspondía leer. [39484547772](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39484547772) también omitió el procesamiento. |
| D. Falló la lectura | [36695397136](https://github.com/SanLean17/parque-movil-ftr/actions/runs/36695397136), 30/09: falla en lector anterior de Drive, `TimeoutError: The read operation timed out`; no ejecutó el guardado. Es antecedente histórico, no causa demostrada del evento de octubre. |
| E. Guardó pero no publicó | No se confirmó un caso real reciente de este tipo en los registros examinados. Se cubre con pruebas que simulan Pages fallido o de otro commit, sin darlo por publicado ni cambiar datos reales. |
| F. Web anterior | Al iniciar, el manifiesto HTTP coincidía con GitHub (`version` 21/10 04:18:44.475436 UTC, solicitud `39543314459`). No se confirmó caché vieja. La reparación añade comparación de bytes de todos los archivos del manifiesto antes de confirmar futuras publicaciones. |

Los logs de la ejecución 39567554012 acreditan `Contents: write`, `Pages: write`, secreto de calendario presente sin revelar su valor y llamada al workflow reutilizable desde `main`. Las entradas de producción `actualizar_parques.yml`, `ftr_sincronizar.yml` y Pages estaban `active`. Los workflows antiguos de activación/auditoría permanecían deshabilitados. No fue necesario cambiar esos estados.

El antecedente [39223175621](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39223175621), 19/10 08:29:54 UTC, sí fue `schedule`: leyó Drive y guardó, omitió CNRT. Su cron histórico era `0 3 * * *`; el arranque registrado fue 5 h 29 min después de esa hora diaria. El workflow antiguo no verificaba HTTP/Pages, por lo que esa evidencia no prueba la publicación de la reparación actual.

La política de leer Drive en cada arranque auténtico `schedule` ya estaba incorporada en la base inicial (cambio de las 11:01 Argentina del 21/10), posterior al evento de las 05:12. Se conserva y se vuelve a probar. No se presenta ese cambio previo como realizado por esta auditoría.

## Defectos reproducidos y correcciones

1. **CNRT confundía códigos con líneas.** `195,2077IE,2077OP1` producía `{195,2077}`; `36OP1` entraba en la línea 36. Se admiten únicamente tokens numéricos completos, incluyendo `195.0`. La empresa compartida se consulta una sola vez y sus vehículos se separan por línea. La validación posterior sigue rechazando dominios duplicados/incorrectos.
2. **CSV incompleto aceptado.** `on_bad_lines="warn"` omitía una fila defectuosa y devolvía éxito. Ahora se comprueba la longitud de todas las filas antes de pandas y se rechaza toda la descarga. El parque anterior queda intacto ante error.
3. **Lista paralela en diagnóstico.** El diagnóstico leía el literal de `configuracion_lineas.py` aunque existiese `_ftr_config.json` con un alta/desactivación. El adaptador y los diagnósticos usan la configuración central validada; la fuente y el período de sus CLI toman lo publicado salvo propuesta explícita de diagnóstico. No se hace fallback a una lista vieja si el JSON central es inválido.
4. **Cobertura pública incoherente.** La portada contaba todos los dominios controlados aunque no pertenecieran al parque actual. Ahora compara la intersección de dominios y cuenta vehículos únicos. Los controles fuera del parque permanecen en los CSV y en el diagnóstico; no se interpretan como bajas.
5. **Error de descarga presentado como cero.** La portada mostraba cero controles y el detalle clasificaba todos como pendientes si fallaba la descarga de controles. Ahora muestra “Lectura no disponible”, sin porcentajes ficticios ni copia de pendientes no comprobados. Una tabla válida vacía sigue siendo cero.
6. **Verificación insuficiente de publicación.** Pages construido no certificaba el contenido que consumía el navegador. El manifiesto futuro contiene SHA-256 de HTML, script público, fechas y todos los CSV activos. Se compara la versión y cada archivo servido por HTTPS, con hasta tres comprobaciones ante propagación. Si falla, la ejecución queda en error/publicación pendiente y se conservan los datos guardados. No se inventa una nueva lectura para hacer pasar esta comprobación.
7. **Visibilidad y cola.** El recibo `operacion.json` y el resumen de Actions distinguen agenda, lectura iniciada/terminada, configuración/datos guardados, publicación pendiente/confirmada y error. Se conserva el nombre del paso que interpreta el cliente 06.3. `queue: max` mantiene ejecuciones próximas en cola en lugar de reemplazar la única pendiente, con exclusión mutua en el coordinador. No se añaden disparadores por `push` de producción ni bucles.

La cola usa la capacidad documentada por [GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency): hasta 100 pendientes; no es una cola infinita ni garantiza puntualidad. La limitación general de `schedule` se documenta en [eventos de Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule); no se utiliza como explicación sin evidencia del incidente.

## Configuración preservada y aplicación 06.3

- Planilla: `1rxhnmA9-fekE8QHPddoalPRK66sHxdKu9jk1R4-lAJk`, período 2026.
- FTR: diario, 17:00; CNRT: cada 5 días, 22:00.
- Zona: `America/Argentina/Buenos_Aires`; ancla 19/10/2026; 48 líneas habilitadas y 34 empresas.
- Cron nativo: `0 20 * * *`, `0 1 * * *`, recuperación `0 3 * * *`, en UTC. Próximo día de CNRT según ancla: 24/10, 22:00 Argentina.
- No se cambian JSON, estado, CSV ni fechas reales en este diff. Agregar/desactivar/quitar líneas no elimina archivos históricos.

El servidor 06.3 envía `action`, `config_json`, `expected`, `request_id` a `ftr_sincronizar.yml` con `ref: main`. Esos campos, las respuestas y los nombres de pasos usados para clasificar resultados se mantienen. Un envío devuelve “Solicitud enviada”; no equivale a guardado. Se conserva el control de huella para rechazar borradores anteriores y el commit conjunto de JSON/YAML: un rechazo del permiso de calendario termina con error sin publicar el nuevo horario. No se amplían permisos ni se cambia ningún secreto. Una actualización de hora puede validarse con datos ficticios; cambiarla realmente para una demostración sustituiría la configuración del usuario y no se realiza.

## Pruebas y límites de la comprobación

Antes de corregir, las cinco regresiones de CNRT/lista central fallaron; las pruebas web reprodujeron conteos y ceros falsos. Con la reparación: **260 tests Python y 24 subpruebas** pasan, más 22 comprobaciones del modelo del panel y tres tests de comparación web. Se validan horarios futuros/pasados, cruce de mes/medianoche, enfriamiento tras error, lectura previa al turno, pausa, frecuencia independiente, secreto rechazado, commit conjunto, conflictos, empresas compartidas, múltiples pestañas, repetición de vehículo, período nuevo, dominio inválido, tabla vacía/faltante y despliegue no confirmado. Google, CNRT, GitHub y Pages están simulados en estas pruebas; el parser, separador, CSV, diagnóstico/cifrado y comparación se ejecutan realmente sobre fixtures.

Prueba en navegador real: 390 y 1280 píxeles, CSV ficticios, botones Copiar controlados/Copiar pendientes, fecha de fiscalización sin hora, actualización general con hora y “hs”, tema oscuro y tratamiento de fuente no disponible. Se preserva el diseño. El CI nuevo ejecuta la batería en Linux y Windows y navegador Chromium en Linux; no tiene secretos de Google/CNRT, no empaqueta un ejecutable ni dispara lecturas reales.

**Pendiente al preparar esta revisión:** observar después de la integración una nueva ejecución auténtica `schedule` que lea fuentes, guarde y publique. La última lectura real de Drive del estado inicial fue 20/10 23:47:36 Argentina y provino de `workflow_dispatch`; no cuenta como validación automática. No se promete vigilancia en segundo plano ni se presenta una prueba manual/push como evidencia del calendario. Una futura ejecución debe acreditarse mediante su URL, evento, cron recibido, hora configurada, comienzo de lectura, fuentes procesadas, commit y verificación HTTP.

## Archivos y reversión

Cambios funcionales: `actualizar_parques.py`, `configuracion_lineas.py`, `_ftr_pruebas/planilla_anual.py`, las tres entradas administrativas, `_ftr_runtime/worker.py`, `_ftr_tools/ejecutar.py`, `index.html`, `linea.html` y `ftr_sincronizar.yml`. Se añaden CI, pruebas, validador e inventario/informe. Se corrige además la portabilidad UTF-8/PATH de una prueba Git de calendario.

Para revertir esta reparación, crear una rama desde el `main` vigente y revertir el commit de integración de esta PR (o sus commits funcionales), revisar el diff y ejecutar las pruebas. La PR no contiene archivos de datos, configuración ni marcas de lectura: revertirla no debe restaurar CSV viejos. Si apareciesen conflictos por cambios posteriores, resolver sólo las líneas de código de la reparación. No usar reset, force-push, restaurar el respaldo completo ni borrar registros. Conservar los commits automáticos posteriores y los informes; si un manifiesto contiene hashes de una versión anterior de HTML, la siguiente publicación validada lo regenerará.
