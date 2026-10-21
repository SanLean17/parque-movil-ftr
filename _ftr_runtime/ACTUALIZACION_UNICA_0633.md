# FTR 06.3.3 — detalle público y actualización única

## Alcance

Dos cambios: simplificar el detalle público de controlados fuera del parque y agregar una cita extraordinaria por fuente en las tarjetas existentes de Actualizaciones. Se conservan el CSS, los botones y componentes existentes, los contadores y las funciones de copia. El detalle administrativo completo sigue disponible.

No se cambian `_ftr_config.json`, `_ftr_estado.json`, `actualizar_parques.yml`, parques, controles, fechas de lectura, enlace de la planilla, período, líneas ni secretos. La entrega inicial tiene una agenda extraordinaria vacía: no deja ninguna cita real programada. Las pruebas no despachan Drive, CNRT, Actualizar todo ni una cita en producción.

## Detalle público

Solo muestra SITUACIÓN, REFERENCIA ACTUAL DEL INTERNO y OBSERVACIÓN. Si no hay referencia: “REFERENCIA ACTUAL DEL INTERNO: No disponible.” Los internos compartidos se presentan como referencias posibles, sin afirmar una baja ni un reemplazo. La tabla y VER DETALLE / CERRAR DETALLE se conservan.

## Almacenamiento y ejecución en GitHub

`_ftr_extraordinarias.json` conserva una cita por fuente en `pending`, sus fechas completas con zona horaria, `history`, `last_execution` y los identificadores de órdenes ya procesadas en `receipts`. No contiene credenciales ni datos administrativos privados.

Programar, cambiar o cancelar guarda únicamente ese registro y el aviso generado en `.github/workflows/ftr_extraordinarias.yml`. El cron usa UTC internamente, con día y mes; la aplicación muestra y valida America/Argentina/Buenos_Aires. El año completo y el identificador persistidos impiden repetir la cita el año siguiente. Sin citas pendientes, el workflow no tiene cron.

GitHub inicia el aviso y llama al coordinador existente `ftr_sincronizar.yml` con acción `oneoff`. El coordinador vuelve a cargar main dentro de la exclusión mutua existente. No se añade otro bloqueo que pueda cancelar o trabar al coordinador. Programar CNRT por sí solo no activa la política de lecturas adicionales de Drive.

Se reutiliza FTR_SCHEDULE_TOKEN para guardar cambios en workflows, con el mismo mecanismo y permisos del calendario existente. La autorización y el guardado del reclamo ocurren antes de leer fuentes. Un rechazo impide la lectura. No se crean ni modifican secretos.

La PC puede apagarse después de que el panel confirme “Guardada en GitHub”. Una orden todavía local necesita que el programa se abra con Internet para enviarse. No se instalan relojes, tareas de Windows, servicios ni cron externos.

GitHub puede demorar o descartar eventos de calendario: [documentación oficial de schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). No se promete puntualidad exacta. El siguiente arranque del coordinador puede recuperar una cita con hasta 24 horas de demora. Si excede ese plazo, se registra ERROR sin leerla y se requiere reprogramación manual. Se permiten fechas futuras hasta 366 días.

## Calendario y coincidencias

La cita no modifica anchor, frecuencia ni horario recurrente. Una lectura puramente extraordinaria conserva por separado la información con que se decide si el turno recurrente fue atendido; actualiza la última lectura real solo si resulta válida. La siguiente lectura recurrente sigue calculándose con la configuración publicada.

Si la cita coincide exactamente con el turno recurrente, una sola lectura sirve a ambos motivos. El aviso posterior comparte el resultado. También se comparte una orden “Actualizar ahora” confirmada mientras la misma fuente estaba ejecutándose, o una cita que llega durante esa lectura. Los identificadores persistidos y el reclamo publicado antes de leer impiden repetir una cita por eventos duplicados. Se conserva la política habitual de lecturas adicionales de Drive en los demás arranques recurrentes.

## Estados, fallos y uso offline

El historial identifica PROGRAMADA MANUALMENTE y distingue lectura guardada, ERROR, cancelación y reemplazo. Los informes de ejecuciones diferencian agenda comprobada, configuración guardada, cita guardada, resultado compartido y lectura/publicación completadas.

Una fuente fallida conserva sus archivos y fecha de última lectura válidos. La cita consumida pasa a ERROR, sin reintento automático. Un proceso interrumpido no puede volver a consumir la misma cita. Un reclamo sin resultado confirmado después del límite de ejecución de 90 minutos, más cinco minutos de margen, se muestra como ERROR; el siguiente guardado del coordinador conserva ese diagnóstico. La publicación se verifica por el coordinador existente y su enlace de ejecución.

La cola local conserva órdenes confirmadas y evita duplicados. Una cita offline no se presenta como guardada en GitHub. Antes del envío se vuelven a comprobar la configuración, el identificador de la cita anterior y que la fecha siga siendo futura. Si venció: “La fecha programada ya pasó. Elegí una nueva fecha y horario.” Cambiar y cancelar afectan solo a esa cita, sin consultar fuentes ni tocar fechas de lectura.

## Archivos de implementación

- Detalle público: `ftr-historial.js`, `ftr-historial-publico.js`.
- Citas, concurrencia y calendario: `_ftr_extraordinarias.json`, `_ftr_runtime/oneoff.py`, `worker.py`, `config.py`, `agenda.py`, `_ftr_tools/ejecutar.py`, `.github/workflows/ftr_extraordinarias.yml`, `ftr_sincronizar.yml`.
- Cliente: `_ftr_app/main0631.py`, `outbox.py`, `agenda_bridge.py`, `panel-bridge.js`, `panel.html`, `server.py`, `LEEME_0631.txt`.
- Verificación y entrega: pruebas de citas y cola, pruebas de integración/agenda existentes, `browser_history.py`, `_ftr_tools/oneoff_browser_checks.py`, `check_panel.py`, `check_client_build.py`, `package_client.py`, `validar_repositorio.py`, `ftr_auditoria_ci.yml` y este informe.
- `ftr_publicacion.json`: solo se renuevan las huellas del código público modificado; se mantienen las fechas reales y la identidad de los datos publicados.

## Validación y Windows

Pruebas locales: 324 pruebas Python y 33 subpruebas aprobadas; 17 casos del modelo histórico, tres de la web y 22 del panel aprobados. Cubren hoy/mañana, fechas pasadas, cambio de mes/año, Buenos Aires, independencia de fuentes, cambio/cancelación, una sola ejecución, frecuencia diaria y de cinco días, coincidencias, fallo de fuente, reclamo interrumpido, fallo al guardar y órdenes offline vencidas.

El navegador comprobó el detalle público y las pantallas existentes, más la nueva sección a 390 y 1280 píxeles en ambos temas, sin desbordamientos ni errores JavaScript. Las órdenes de esas pruebas permanecen en entornos temporales simulados. El CSS original se conserva y las pruebas verifican que los campos recurrentes no se alteren al operar las citas.

La compilación nueva es FTR Administración 06.3.3. Conserva conexión, cola, borradores y recuperación de informes privados de 06.3. No necesita Python instalado. El paquete final contiene ocho archivos, VERSION.json y comprobantes SHA-256 incluidos; no contiene llaves, tokens ni informes del usuario. La validación CI exige Linux y Windows, prueba el ejecutable compilado y entrega un único paquete estable de esta versión.
