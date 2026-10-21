# Auditoría de agenda FTR — 21/10/2026 — reparación 06.3.4

## A. Caso real de las 17:00

Base auditada: `872cbc8b13618f79c9ca6061296847285adc3471`, rama predeterminada `main`. Corte de evidencia anterior a la reparación: **21/10/2026 17:36:28 Argentina / 20:36:28 UTC**. La API no registraba ninguna ejecución `schedule` posterior a las 08:12:40 UTC. No había ejecución de las 17:00 en espera, cancelada, omitida ni fallida: faltaba una ejecución registrada para ese turno. La API no expone la cola interna del programador; no permite distinguir un evento todavía retenido de uno descartado internamente.

El horario estaba bien guardado y publicado. El workflow estaba activo, Actions habilitado, las acciones permitidas y `main` era la rama predeterminada. No encontramos un error de conversión horaria ni una cancelación por concurrencia que explique la ausencia de esa ejecución. Esto no convierte el JSON correcto en prueba de puntualidad: al corte el turno seguía **pendiente y atrasado**.

No se inició Drive, CNRT ni «Actualizar todo» manualmente durante esta auditoría. Las ejecuciones manuales de la tabla pertenecen a trabajo anterior y se incluyen como evidencia histórica.

### Cronología comprobada

Los valores son `created_at / run_started_at / updated_at` de GitHub, todos UTC. No se los confunde con el inicio real de la lectura. El archivo [evidencia_agenda_20261021.json](evidencia_agenda_20261021.json) conserva los SHA completos, estados, pasos y tiempos de 11 ejecuciones relevantes, además de las 50 ejecuciones programadas visibles en el historial consultado.

| Fecha | Ejecución / evento | Creada / iniciada / actualizada UTC | Commit | Fuentes y resultado |
|---|---|---|---|---|
| 17/10 | [39013983359](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39013983359), schedule antiguo | 07:31:59 / 07:31:59 / 07:34:02 | f913e2a | Drive ejecutado; CNRT omitido; éxito |
| 18/10 | [39108956459](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39108956459), schedule antiguo | 07:46:56 / 07:46:56 / 07:55:43 | 3149ce3 | Drive y CNRT ejecutados; éxito |
| 19/10 | [39223175621](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39223175621), schedule antiguo | 08:29:54 / 08:29:54 / 08:32:06 | cf45433 | Drive ejecutado; CNRT omitido; éxito |
| 20/10 | [39351534215](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39351534215), push de integración anterior | 01:06:07 / 01:37:55 / 01:46:11 | 059b8c0 | Última lectura CNRT conservada: 01:38:31.860499; completada 01:45:18.606665 |
| 20/10 | [39377807130](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39377807130), schedule | 05:59:07 / 05:59:07 / 05:59:15 | 0e964d8 | Comprobó agenda; proceso omitido; éxito sin lectura |
| 20/10 | [39412478671](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39412478671), schedule | 11:05:22 / 11:05:22 / 11:05:34 | 0e964d8 | Comprobó agenda; proceso omitido; éxito sin lectura |
| 20/10 | [39450292231](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39450292231), schedule | 15:38:31 / 15:38:31 / 15:38:44 | 0e964d8 | Comprobó agenda; proceso omitido; éxito sin lectura |
| 20/10 | [39484547772](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39484547772), schedule | 19:34:00 / 19:34:00 / 19:34:11 | 0e964d8 | Comprobó agenda; proceso omitido; éxito sin lectura |
| 21/10 | [39534950424](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39534950424), workflow_dispatch previo | 02:47:17 / 02:47:17 / 02:48:28 | 3e8f257 | Drive leído a 02:47:36.346776; completado 02:47:41.132797; guardado y publicado |
| 21/10 | [39543314459](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39543314459), workflow_dispatch config | 04:18:29 / 04:18:29 / 04:19:32 | e964e73 | Guardó hora 17:00 y calendario; fuentes seleccionadas: ninguna |
| 21/10 | [39567554012](https://github.com/SanLean17/parque-movil-ftr/actions/runs/39567554012), schedule | 08:12:40 / 08:12:40 / 08:12:49 | d23bebc | Agenda comprobada; fuentes ninguna; lectura y publicación omitidas |
| 21/10 | Turno esperado Drive | **20:00:00 UTC = 17:00 Argentina** | main | Sin ejecución registrada hasta el corte 20:36:28 UTC |

El cambio real de horario quedó en [d23bebc](https://github.com/SanLean17/parque-movil-ftr/commit/d23bebc0e85c773642d3d3b5e65260a9cc78cb82), a **04:18:44 UTC / 01:18:44 Argentina**, junto con `_ftr_config.json` y el workflow. `schedule_effective_from_utc`: `2026-10-21T04:18:44.468372+00:00`. Los cron publicados eran `0 20 * * *`, `0 1 * * *` y `0 3 * * *`.

La última lectura Drive era **20/10 a las 23:47:36 Argentina**, anterior al nuevo turno. Su `served_slot` era `db7d7a37123f:2026-10-20T22:00:00-03:00`, correspondiente al calendario anterior. Ni esa lectura ni el guardado de la configuración satisfacen el 21/10 a las 17:00. No había citas extraordinarias ni historial de citas en el estado real.

La ejecución de 08:12 UTC / 05:12 Argentina utilizó d23bebc y la política vigente entonces. La lectura adicional en todo arranque automático se incorporó después; no se atribuye retroactivamente a ese código. El cron de origen no quedó registrado de manera recuperable en los logs antiguos revisados: no adjudicamos esa ejecución arbitrariamente al cron de 01:00 o de 03:00 UTC.

El historial de cambios del archivo de calendario no muestra reescrituras posteriores a d23bebc antes del corte. Los PR posteriores cambiaron el coordinador y el cliente; no volvieron a modificar esas expresiones. El `updated_at` del registro API del workflow refleja su estado administrativo y no sustituye el historial Git del YAML. No hay evidencia que permita atribuir el caso a un supuesto «reinicio del reloj» por merges.

## B. Problemas bajo nuestro control

1. **Recuperación demasiado distante:** si se perdía el disparador de Drive, solo quedaban los siguientes horarios del calendario y el control nocturno. Podían pasar horas.
2. **Confirmación incompleta en el cliente:** tener una configuración guardada no comprobaba el estado enabled/disabled, la rama predeterminada ni el contenido remoto de todos los calendarios.
3. **Publicación sin recuperación independiente:** una lectura podía quedar atendida en el estado aunque Pages fallara después; el próximo control podía omitir la fuente sin reintentar esa publicación.
4. **Falta de trazabilidad uniforme:** los turnos recurrentes no conservaban un historial explícito de hora prevista, evento recibido, lectura real, demora y recuperación.
5. **Coincidencias y avisos repetidos:** un aviso principal tardío podía convertirse en otra lectura adicional de Drive pese a que manual o recuperación ya hubiesen atendido ese turno. Al incorporar la unión por hora del evento se probó y corrigió además el caso 16:58 → 17:03: terminar después de las 17:00 no convierte una lectura iniciada antes en la lectura del nuevo turno.

Son defectos o carencias verificables, corregidos con pruebas. **No se los presenta como causa demostrada de la ausencia del evento de las 17:00**, porque ninguno llegó a ejecutarse en un run de ese turno al corte.

## C. Corrección y funcionamiento

- Conservamos el calendario principal generado desde el panel. Guardar sigue siendo una transacción conjunta de configuración y YAML; una denegación de push no se presenta como guardado exitoso.
- Agregamos `ftr_recuperar_turnos.yml`, estable, con `7,22,37,52 * * * *`. Invoca el mismo coordinador en modo `recovery`. Solo atiende recurrentes vencidos, citas pendientes dentro de su vigencia y publicaciones pendientes. No añade lecturas a cada comprobación.
- Se conserva la política de lecturas adicionales Drive en los arranques válidos del calendario original, con protección de duplicados y del turno principal. CNRT nunca se fuerza por esa regla.
- Un solo grupo `ftr-publicacion-validada`, `cancel-in-progress: false`, `queue: max`, reside en el coordinador. Los tres padres carecen de otro bloqueo. Todos consultan el estado actualizado de `main` al obtener su turno. Pages no comparte ese bloqueo ni consulta fuentes. La cola máxima de GitHub tiene un límite de 100 pendientes; no se promete capacidad infinita.
- El estado de publicación se guarda como pendiente antes de publicar. El resultado se confirma tras Pages y la comprobación de archivos servidos. Ante fallo, el próximo control vuelve a publicar los archivos guardados sin repetir una lectura ya satisfecha. La confirmación posterior es un commit de estado, sin mover `read_utc` ni archivos de fecha.
- El historial conserva hasta 200 ejecuciones: fuente, run, acción, cron recibido, creación del evento, hora prevista, comienzo/fin, lectura real, demora, estado y error. El límite evita crecimiento indefinido; el historial completo de runs permanece en Actions según su retención.
- Un reclamo interrumpido se considera sin resultado confirmado después de 95 minutos, por encima del timeout de ejecución de 90. Un recurrente pendiente puede recuperarse; las citas únicas consumidas no se reejecutan automáticamente. Los fallos de fuente conservan el último resultado válido y la espera de reintento de una hora.
- El panel comprueba workflows, rama y contenido remoto exacto de calendario principal, extraordinario y recuperación. Si falta acceso o respuesta, muestra «sin verificar»; si está deshabilitado o desajustado lo informa. Después de guardar, se verifica la revisión real y no se confirma activación si falla esta comprobación. Esta verificación comprueba disponibilidad administrativa y contenido, no garantiza la entrega futura de un evento.
- El panel muestra próximo turno, último evento, última lectura, hora prevista/real, recuperación y error. A los 30 minutos de un turno sin lectura muestra **ACTUALIZACIÓN ATRASADA**. Si falta la comprobación web muestra **PUBLICACIÓN PENDIENTE**.

La PC solo configura y consulta. Una orden todavía pendiente de envío local necesita abrir el cliente con conexión; una programación ya publicada se ejecuta en GitHub con la PC apagada.

## D. Archivos y límites de cambio

Calendarios: `.github/workflows/actualizar_parques.yml`, `ftr_extraordinarias.yml`, `ftr_sincronizar.yml`, nuevo `ftr_recuperar_turnos.yml`; validación y compilación: `ftr_auditoria_ci.yml`.

Coordinación: `_ftr_runtime/{agenda,config,native_schedule,oneoff,worker}.py`, nuevos `schedule_health.py`, `publication_retry.py`; `_ftr_tools/ejecutar.py`.

Cliente: `_ftr_app/{main0631,agenda_bridge,outbox,server}.py`, `panel-bridge.js`, `panel.html`, `LEEME_0631.txt`. Se conserva el diseño y la recuperación local de informes privados. Paquete estable 06.3.4.

Pruebas/empaquetado: `test_recovery.py`, `test_config_transaction.py`, `test_schedule_reads.py`, `test_agenda_bridge.py`, `recovery_browser_checks.py`, `oneoff_browser_checks.py`, `check_panel.py`, `check_client_build.py`, `package_client.py`, `validar_repositorio.py`; este informe y su evidencia JSON.

El PR no cambia `_ftr_config.json`, `_ftr_estado.json`, `_ftr_extraordinarias.json`, planilla, período, anchor, líneas, parques, controles, historial público ni fechas reales. En el calendario principal conserva las expresiones cron y solo añade el permiso de lectura de Actions requerido por la observabilidad. Los tests usan datos simulados. Un evento automático futuro podrá producir los cambios legítimos de datos habituales.

## E. Revisión y entrega

Rama de reparación: `ftr/agenda-recuperacion-verificable`, desde 872cbc8. El PR contiene el diff completo, revisión y CI Linux/Windows; su enlace y los SHA definitivos se consignan en la devolución de entrega. No se hace force-push ni se restaura código anterior defectuoso. La compilación incluye VERSION.json con el SHA y comprobantes SHA256 de archivos.

## F. Pruebas

Validación local: **350 pruebas Python y 33 subpruebas**; JavaScript: 17 casos de historial, 3 de web y 22 del modelo de panel. El panel se probó en 390/1280 px, temas claro/oscuro, con estado activo, deshabilitado, no verificable, atrasado, recuperado y publicación pendiente; sin errores JS ni solicitudes externas. La prueba HTTP local requirió salir del aislamiento que bloqueaba loopback (WinError 10013), y pasó con la misma prueba habilitada.

Los 26 casos nuevos de `test_recovery.py`, junto a la suite previa de agenda y extraordinarias, cubren los 25 requisitos solicitados:

| Requisitos | Cobertura |
|---|---|
| 1–5 | Turno diario 17:00; exacto, +2, +30 minutos; recuperación posterior y pasada medianoche |
| 6–7, 20 | Extraordinaria antes/después; coincidencia exacta comparte lectura sin mover recurrencia |
| 8–11 | Cambio de hora elimina cron anterior; nueva frecuencia/fingerprint; cambio de día y 22:00 AR → 01:00 UTC siguiente |
| 12–15 | CNRT 3/5 días, cruce de mes y año; fuentes con horas iguales/diferentes |
| 16–18 | Workflow deshabilitado, permisos denegados, rama/cron incoherentes; contrato de cola única sin cancelación padre/hijo |
| 19, 21–23 | Manual/automático coincidentes, turno atendido, lectura vieja, mismo ID repetido, evento en cola |
| 24–25 | Reclamo cancelado/interrumpido; fallo de publicación recuperado sin releer; error de fuente conserva archivos |
| Regresión adicional | Lectura 16:58–17:03 no satisface el turno 17:00, aun si su evento llegó durante esa lectura |

Las pruebas de concurrencia validan el contrato YAML y las intercalaciones simuladas; no simulan la infraestructura interna de colas de GitHub. CI valida de nuevo y prueba el ejecutable Windows empaquetado. Las pruebas simuladas no son evidencia de una lectura real automática.

La primera corrida del PR detectó un resultado intermitente en la comprobación Windows de la cita única (la corrida de rama pasó). Se reforzó la sincronización de esa prueba: espera la respuesta POST concreta y su identificador visible, en vez de inferir la orden a partir del último elemento y de un título que podía pertenecer a otra fila. Conserva las mismas aserciones de fuente y estado pendiente. El ejecutable descargado de CI pasó localmente con esa comprobación; la entrega exige además nuevas corridas verdes del PR y main.

## G–H. Programación conservada

| Fuente | Configuración Argentina | Cron UTC | Selección |
|---|---|---|---|
| Drive | Cada día, 17:00 | `0 20 * * *` | Turno diario; pendiente del 21/10 al corte |
| CNRT | Cada 5 días, 22:00; anchor 19/10/2026 | `0 1 * * *` | El coordinador calcula 19/10, 24/10, 29/10…; próximo 24/10 22:00 AR = 25/10 01:00 UTC |
| Control nocturno original | 00:00 AR | `0 3 * * *` | Conservado |
| Recuperación complementaria | Minutos 07, 22, 37, 52 de cada hora | `7,22,37,52 * * * *` | Solo pendientes, sin lecturas adicionales por cada control |

No se usa `*/5` en el día del mes. Horas iguales generan una sola expresión principal. Las citas únicas tienen su workflow propio y pasan por la misma cola; no reinician el anchor. No se creó una cita real para probar.

## I. Inventario completo

Estado administrativo leído por API antes de la reparación:

| Workflow | Estado | Triggers / función |
|---|---|---|
| actualizar_parques | activo | schedule + dispatch; padre recurrente, llama al coordinador |
| ftr_sincronizar | activo | workflow_call + dispatch; único ejecutor/publicador; sin schedule ni push |
| ftr_extraordinarias | activo | dispatch; schedule solo cuando hay citas; padre, sin citas reales al corte |
| ftr_recuperar_turnos | nuevo en este PR | schedule + dispatch; padre de recuperación, mismo coordinador |
| ftr_auditoria_ci | activo | PR/main y push filtrado; fuentes ficticias y compilación; sin secretos de fuentes |
| pages-build-deployment | activo, gestionado por GitHub | Publica; no llama a fuentes ni usa su bloqueo |
| ftr_calendario_nativo_pruebas | activo, histórico | push solo `ftr/lectura-en-arranques`; sin schedule, sin disparador en main; reemplazado por CI integral |
| ftr_respaldo064_pruebas | activo, histórico | push solo `ftr/respaldo-pc-064`; sin schedule, sin disparador en main; reemplazado por CI integral |
| ftr_agenda_pruebas062 | deshabilitado manualmente | Pruebas históricas, sin producción vigente |
| ftr_correccion061 | deshabilitado manualmente | Pruebas históricas |
| ftr_integracion_pruebas | deshabilitado manualmente | Pruebas/empaquetado históricos |
| ftr_reparacion063_pruebas | deshabilitado manualmente | Pruebas históricas |
| probar_planilla_anual | deshabilitado manualmente | Prueba antigua de fuente, no utilizada |
| ftr_activar_calendario063 | deshabilitado; archivo ya retirado | Activación puntual histórica |
| ftr_auditoria_integral063 | deshabilitado; archivo ya retirado | Auditoría histórica |
| ftr_mantenimiento_agenda | deshabilitado; archivo ya retirado | Mantenimiento histórico |
| ftr_recuperar_planilla_solicitada | deshabilitado; archivo ya retirado | Recuperación puntual anterior |

Se conserva el historial. Los dos workflows de pruebas todavía activos solo reaccionan a ramas antiguas explícitas: no intervienen en main, no tienen reloj ni consultan fuentes reales. No se los confunde con producción ni se necesita activarlos. Los nueve registros antiguos ya deshabilitados permanecen así. La evidencia JSON conserva los triggers exactos de la base.

Actions administrativos: `enabled=true`, `allowed_actions=all`, permisos predeterminados de workflow `write`, aprobación de PR por Actions `false`. Consulta GET autorizada por el usuario, sin mostrar/guardar credenciales ni cambiar permisos. Los permisos efectivos del coordinador son contents/write, pages/write y, desde la reparación, actions/read. No se modificaron secretos ni sus autorizaciones. La escritura del YAML sigue usando el permiso existente FTR_SCHEDULE_TOKEN; si falta, se rechaza el cambio de horario.

## J–K. Comparación y arquitectura elegida

| Aspecto | Anterior a administración | Base 06.3.3 / reparación 06.3.4 |
|---|---|---|
| Activación | Un schedule `0 3 * * *`, dispatch | Horarios del panel en UTC + recuperación nocturna; se añade control estable de pendientes |
| Rama | Default branch | Default `main` comprobada; checkout explícito de main al ejecutar |
| Ejecutor | Job directo | Padres llaman a un coordinador reutilizable; existe evidencia de llamada automática exitosa el 21/10 08:12 |
| Permisos | contents/write | contents/write + pages/write; lectura Actions para evidencia; permiso especial de workflows solo al cambiar calendario |
| Concurrencia | Sin exclusión propia | Una cola sin cancelación; ninguna duplicada en padre/hijo |
| Frecuencia CNRT | 15 días según última descarga | 5 días según anchor y hora; no se desplaza por manual ni extraordinaria |
| Drive | Lee en cada llegada | Valida fuente anual y período; conserva política adicional solicitada y obligación del turno principal |
| Guardado | `git add .` y push | Staging de resultados válidos, rutas explícitas, configuración+YAML juntos, sin forzar Git |
| Publicación | Consecuencia del push; sin confirmación completa propia | Pages solicitado explícitamente y hashes públicos verificados; ahora recuperación independiente y recibo de estado |
| Fechas | Scripts separados de actualización | Inicio real `read_utc`, fin `completed_utc`, intento separado; publicación nunca simula otra lectura |
| Push de código | Sin lectura en el workflow antiguo | La integración intermedia tuvo push; ya eliminado de los workflows de fuentes antes de esta reparación |

El mecanismo anterior arrancaba solo, pero el 17, 18 y 19/10 lo hizo **4 h 31 m 59 s, 4 h 46 m 56 s y 5 h 29 m 54 s** después del único cron 03:00 UTC. Esa comparación refuta que antes existiera puntualidad garantizada; tampoco prueba que toda demora actual tenga una única causa.

Se eligió **calendario principal dinámico + recuperación estable + un solo coordinador**. La separación permite cambiar horarios desde el cliente sin reescribir el control de recuperación. Los despertares complementarios no son dos ejecutores competidores: todos consultan el mismo estado y esperan en la misma cola. No hay llamadas circulares ni disparadores push para leer fuentes.

Alternativas consideradas dentro de GitHub:

- Un único cron frecuente que decida todo: evita editar horarios en YAML, pero no refleja el horario exacto solicitado como disparador principal; no se eligió.
- Más cron en el mismo archivo dinámico: posible, pero mezcla recuperación con cada reescritura del calendario; se eligió un archivo estable separado.
- `workflow_run`, re-run o auto-dispatch: pueden reaccionar a una ejecución existente, pero no generan evidencia de un evento ausente; el encadenamiento añade riesgo de bucles. No se eligieron como reloj.
- Un job durmiendo hasta la hora: consume runner y tiene límites de duración; deja otro punto de fallo. No se eligió.
- Recuperación externa/PC encendida: excluidas por el usuario.

GitHub controla la entrega del evento, asignación del runner y disponibilidad de Actions/Pages. El repositorio controla cron, activación comprobable, selección, deduplicación, cola, datos válidos, reintentos, trazabilidad y verificación pública. Incluso con esta reparación, **15 minutos es la cadencia solicitada, no un plazo máximo garantizado**. Si GitHub no entrega ningún disparador, ningún workflow puramente interno puede despertarse por su cuenta.

Fuentes primarias: [schedule y demoras/descartes, rama predeterminada e inactividad](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [concurrencia y cola](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), [workflows reutilizables](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations), [eventos originados por tokens](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow), [habilitar/deshabilitar workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows?tool=cli). La suspensión por 60 días de inactividad puede aplicar a repositorios públicos, pero no ocurrió aquí: había commits y workflows activos. El panel detecta la deshabilitación cuando se consulta; no puede reactivar mágicamente GitHub si todos los relojes están apagados.

## L. Evidencia que falta

Este corte demuestra la ausencia de una ejecución registrada hasta las 17:36 y la existencia de defectos reparables. No demuestra la causa interna de GitHub ni que el nuevo control ya haya recibido un evento real: todavía no estaba en main en el corte.

Para cerrar la comprobación operativa se necesita observar un `schedule` natural con esta versión, su selección de Drive pendiente, lectura validada, publicación comprobada y estado recuperado con las horas verdaderas; después, observar el próximo turno ordinario y CNRT en su fecha. No se sustituye esa evidencia por un dispatch manual. La devolución final diferencia lo que ya se observó durante la entrega de lo que permanece pendiente. No se promete puntualidad exacta que GitHub no garantiza.
