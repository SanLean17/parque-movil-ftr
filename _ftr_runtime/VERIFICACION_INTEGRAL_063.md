# Verificación integral FTR — continuación de la PR #9

## Base y alcance

Comprobación del 21/10/2026. La PR #9 está fusionada en `d8822620a4a0fec4c80deffa6f91ead85bb16339`; al iniciar esta continuación no había cambios posteriores en `main`. Se verificó nuevamente `69088bd844df11865cf5f5790dd18e13b251674e` (19/10/2026 08:32:02 UTC, actualización anterior al panel). El inventario y recorrido de producción de `INVENTARIO_WORK_20261021.md` y `AUDITORIA_WORK_20261021.md` siguen siendo la base; esta revisión agrega los archivos enumerados abajo.

Se conservaron las reparaciones de la PR #9: separación exacta de líneas CNRT, CSV estrictos, configuración central, cobertura por dominio del parque actual, errores sin falsos ceros y confirmación HTTP posterior a Pages. No se modificaron la planilla, los CSV laborales, las fechas de lectura ni la configuración publicada. No se disparó una lectura extraordinaria de producción.

La conexión GitHub devolvió permisos de lectura/escritura para este repositorio. Se trabajó en `ftr/verificacion-integral-063`. Ningún cambio de credenciales, permisos, DNS, otro repositorio o instalación del usuario forma parte de esta revisión.

## Defectos reproducidos y correcciones

1. **Órdenes no persistentes en el cliente.** `server.submit` enviaba directamente; un corte podía perder la orden o dejar aceptación incierta. El nuevo motor `main0631.py` guarda primero la orden confirmada. Los borradores no se transmiten automáticamente. Cada orden conserva su identificador y la huella de la configuración revisada. Las solicitudes iguales pendientes se agrupan; un bloqueo entre procesos impide que dos ventanas envíen la misma orden. El envío con respuesta perdida se consulta por identificador, sin repetirse automáticamente.
2. **Conflicto entre computadoras.** Las lecturas manuales ahora pueden llevar `expected` y el coordinador lo vuelve a validar al arrancar. Un cambio remoto posterior detiene la orden, también si llegó mientras esperaba en GitHub. La cola puede expresar una dependencia explícita: primero configuración, luego lectura, solo después de confirmar la operación anterior. Una orden de más de siete días exige revisión. No se modifica la agenda para acomodar una lectura manual.
3. **Estado local de revisiones diferentes.** El motor 06.3.1 consulta configuración y estado usando el mismo commit inmutable. Consulta más de los seis eventos visibles del panel para recuperar órdenes. Una ejecución verde sin procesamiento no confirma una orden de actualización.
4. **Caracteres que parecían dominios válidos después de normalizar.** `Aß123` se convertía en `ASS123`, `AA123ſſ` en `AA123SS` y `\d` admitía cifras no ASCII. Se valida antes de convertir a mayúsculas y solo se admiten números ASCII. La N sigue siendo válida; la Ñ original se conserva en la incidencia, sin corrección automática.
5. **Tablas omitidas.** Una tabla FECHA/DOMINIO/INTERNO sin identidad de línea solo generaba una nota y podía pasar. Ahora requiere revisión. Una pestaña desconocida con encabezados parciales también se identifica. Las pestañas sin tabla se registran; el tablero conocido continúa excluido para no duplicar controles.
6. **Error de otro año que bloqueaba el período elegido.** El lector validaba el dominio antes de excluir una fecha de otro período, en contradicción con el diagnóstico ampliado. Ambos excluyen primero los registros cuyo año está determinado y es distinto. Una fecha no interpretable sigue siendo error.
7. **Referencia insuficiente de sugerencias.** Cada incidencia agrega archivo, SHA-256 y fecha de lectura del parque comparado. Los candidatos siguen limitados al mismo interno y línea, con advertencia de reasignación. Una nueva lectura válida reconstruye incidencias; no conserva como error actual la celda ya corregida.
8. **Publicación parcial visible.** `ftr-datos.js` carga un único manifiesto y verifica cada CSV y fecha antes de usarlos. Un archivo de otra versión o una línea deshabilitada produce estado no disponible. Portada y detalle no presentan como cobertura una mezcla detectada. El manifiesto de mantenimiento incorpora las huellas de los bytes guardados en Git, sin cambiar fechas o afirmar una nueva lectura.
9. **Detalle con ceros tras fallar el parque.** La descarga fallida dejaba contadores iniciales y botones de copia habilitados. Ahora usa el mismo estado no disponible que un fallo de controles. Los campos de las filas se escapan como texto y el parámetro de línea se valida, evitando interpretar contenido de CSV como HTML.
10. **Espera de reintento eludida por una lectura adicional.** Se conserva la lectura extra de Drive en arranques `schedule`, pero también se respeta una hora mínima después de un error. Se registran cron, solicitud, turno, tipo de lectura, inicio y final. Las horas publicadas no se alteran.
11. **Persistencia local.** Borradores, órdenes y autorización usan escritura temporal y reemplazo atómico. La credencial GitHub sigue protegida por DPAPI. El cliente reutiliza la clave de informes existente y guarda una copia protegida por DPAPI solo después de descifrar correctamente. No rota ni elimina la clave original. Los nuevos informes locales se guardan protegidos; los anteriores se conservan para compatibilidad.

## Base Windows y límite de la entrega

Se localizó y descargó el artefacto `ftr-programa-windows-063`, ID `12308144960`, de la ejecución `39517663938`, commit `c7108928afffa9f674c4fd61496c162a225c82c8`.

SHA-256 del ZIP: `180e56b880158e7fcee568aced839aa3e4bba8e97f16a959ab4f1e28fd92c8c7` (coincide con GitHub).

Contiene `FTR_Administracion.exe`, comprobantes de prueba, alcance y `ftr-fuentes-063.zip`. **No contiene `panel.html`.** El workflow original lo reemplaza por una plantilla de prueba y la elimina antes de subir el artefacto. Tampoco se encontró el HTML privado en las ramas relevantes. Los documentos del propio proyecto describen una entrega privada separada, con datos administrativos; ese contenido no debe publicarse indiscriminadamente en GitHub.

El nuevo motor tiene versión **06.3.1**, conserva la carpeta `FTR_Administracion` y no importa ni activa el reloj opcional 06.4. Se reutilizan únicamente sus funciones genéricas de escritura y bloqueo, sin crear tareas de Windows ni temporizadores de fuentes. La cola solo transmite órdenes ya confirmadas mientras el programa está abierto. La agenda publicada continúa enteramente en GitHub.

La CI compila el motor y prueba el ejecutable real en Windows con una **plantilla mínima de prueba**, sesión HTTP, DPAPI, órdenes, cancelación y cierre. Esto no acredita la interfaz original ni su compatibilidad visual. **Hace falta el `panel.html` original o el paquete completo 06.3 para conectar los controles visibles de pendientes/cancelación, verificar el diseño y entregar UN paquete completo.** No se entrega un ZIP incompleto como producto final. No se inspeccionó la instalación del usuario.

La autenticación vencida conserva la orden y espera reconexión expresa; tres envíos rechazados detienen nuevos intentos. Una respuesta ambigua nunca se transforma en “no enviada” ni se reenvía sola. El cierre durante un envío deja una marca recuperable. Un informe de GitHub confirma procesamiento/publicación solo si el paso correspondiente terminó correctamente.

## Configuración observada

Fuente de verdad: `_ftr_config.json`, huella `3819cb72da178af3d2548a42649e47c41d285087615d682817b1f35583a97d55`.

- Período 2026; planilla con identificador `1rxhnmA9-fekE8QHPddoalPRK66sHxdKu9jk1R4-lAJk`.
- 48 líneas habilitadas; 34 empresas.
- Drive: cada 1 día, 17:00 hs. CNRT: cada 5 días, 22:00 hs.
- Zona America/Argentina/Buenos_Aires; ancla 19/10/2026.
- Cron diario UTC: `0 20 * * *`, `0 1 * * *`, `0 3 * * *`. El coordinador calcula el intervalo desde el ancla, no desde días del mes ni desde la última lectura manual.
- Drive puede leerse varias veces al día por los arranques automáticos adicionales habilitados. “Cada 1 día” describe el turno principal, no un máximo de lecturas.
- La frecuencia CNRT permanece independiente. Con esta configuración, el siguiente turno principal CNRT es el 24/10/2026 a las 22:00 hs.

## Pruebas de aceptación y límites

Se ejecutan pruebas con archivos y fuentes ficticios; las llamadas a Google/CNRT/Git/Pages se sustituyen en las pruebas de transacción. Se usan realmente el lector, el diagnóstico, la separación CNRT, el generador de CSV/HTML y el cálculo de estado. No son lecturas laborales ni publicaciones de datos reales.

| Requisitos de la orden | Evidencia reproducible | Alcance |
|---|---|---|
| 1–6: horarios, cinco a tres días, cruces, pausa, demora, extras | `test_native_schedule.py`, `test_agenda062.py`, `test_agenda063.py`, `test_schedule_reads.py` | Reloj y Git simulados; YAML vigente comprobado; no cambio extraordinario de horario real |
| 7–9: alta sin CSV previo, empresa compartida, desactivar/reactivar | `test_config_transaction.py`, `test_audit_regressions.py` | Flujo completo sobre repositorio temporal; conserva archivos históricos |
| 10–12: nueva fuente, denegación, año nuevo vacío | `test_config_transaction.py`, `test_source_pipeline.py` | Exportación simulada; denegación conserva configuración, estado y CSV anteriores |
| 13–16: tablas, repeticiones, CSV roto, códigos alfanuméricos | `test_planilla_anual.py`, `test_audit_regressions.py`, `test_integral_sources.py` | Fuentes ficticias; 195 no se confunde con 2077IE/OP1 |
| 17–18: sugerencias y resolución | `test_integral_sources.py`, pruebas administrativas, `test_modelo_panel05.cjs` | Ñ original, N válida, candidatos y resolución; UI original pendiente |
| 19: fallo de fuente/publicación sin ceros | `test_publication.py`, `browser_public_smoke.py` | HTTP simulado y navegador real; rechazo de archivos con huella distinta |
| 20–24: simultaneidad, sin Internet, reapertura, conflicto, vencimiento | `test_outbox.py`, `test_client_integral.py`, `check_client_build.py` | Disco real, GitHub simulado, binario Windows con plantilla mínima |
| 25–26: cobertura y bytes servidos | `test_public_web.cjs`, pruebas administrativas, navegador y verificación HTTP posterior al despliegue | Cobertura usa línea/dominio; estados y totales históricos separados |
| 27: compatibilidad visual 06.3 | Artefacto original incompleto | Pendiente de `panel.html` privado original |
| 28: paquete final Windows | Compilación/prueba del motor en CI | No equivale al paquete completo con interfaz original |

Las capturas de detalle público a 390 y 1280 px coinciden píxel a píxel con las capturas de la PR #9, con los mismos datos ficticios y modo oscuro. Se comprobaron también copias, fechas y estados de error. No se cambiaron estilos, colores, fuentes ni distribución de pantallas.

## Estado real de automatización

La última ejecución `schedule` observada al iniciar esta revisión es `39567554012`, 21/10/2026 08:12:40 UTC (05:12:40 hs Argentina). Su paso de procesamiento fue omitido. Es una comprobación de agenda, **no una lectura automática completa**. La política de lecturas extra posterior a ese evento queda preservada.

La última lectura Drive registrada sigue siendo `39534950424`, manual, 21/10/2026 02:47:36 UTC; CNRT, `39351534215`, evento push histórico, 20/10/2026 01:38:31 UTC. No se modifican esos tiempos para aparentar actividad. Publicar esta reparación de código no constituye una nueva lectura.

No se atribuye la falta de un evento nuevo a saturación, permisos o caché sin prueba. Hace falta observar un `schedule` auténtico que lea, valide, compare y confirme publicación. Una suite verde o el despliegue de esta reparación no reemplaza esa evidencia. No se configura ni promete vigilancia futura.

## Archivos y reversión

- Lector y diagnóstico: `_ftr_pruebas/planilla_anual.py`, `_ftr_admin/diagnostico_administrativo.py`.
- Coordinación: `_ftr_runtime/worker.py`, `_ftr_tools/ejecutar.py`, `ftr_sincronizar.yml` (solo metadatos de evento; permisos y calendario intactos).
- Web: `ftr-datos.js`, `ftr-publica.js`, `index.html`, `linea.html`, `ftr_publicacion.json` (huellas, sin nuevas fechas).
- Cliente: `server.py`, `main0631.py`, `outbox.py`, utilidades atómicas de `local_clock.py`; pruebas correspondientes.
- Validación: CI integral, pruebas de transacción/fuentes/cliente, navegador, `check_client_build.py`, `manifest_from_git.py`, `validar_repositorio.py`.

Para revertir, crear otra rama desde el `main` vigente y restaurar únicamente el código afectado a la revisión anterior a esta PR. **No restaurar `_ftr_config.json`, `_ftr_estado.json`, CSV o fechas desde una revisión antigua.** Regenerar las huellas del manifiesto con los archivos y configuración vigentes, ejecutar pruebas, revisar la PR y confirmar la publicación. No hacer force-push. En Windows, conservar la carpeta de datos local, las autorizaciones, la clave original y la cola; no ejecutar la versión anterior como si pudiera transmitir las órdenes nuevas pendientes. No se elimina ningún historial para revertir código.
