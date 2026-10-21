# Programación nativa: el panel configura, GitHub ejecuta

## Cambio solicitado

La aplicación 06.3 existente envía su configuración mediante la acción `config`. No necesita descargarse otro ejecutable, quedar abierta ni actuar como reloj. El respaldo local opcional de 06.4 no es requisito de este diseño y no se activa.

Antes, cambiar el horario modificaba `_ftr_config.json`, pero el cron era fijo y comprobaba periódicamente esa configuración. Ahora `native_schedule.render()` genera `.github/workflows/actualizar_parques.yml` con las horas publicadas y `commit_validated()` guarda el JSON y el YAML en el mismo commit. No se modifica el diseño ni el lector.

Los cron usan UTC: 17:00 de Argentina corresponde a `0 20 * * *`, y 22:00 corresponde a `0 1 * * *`. Si las dos fuentes tienen la misma hora se genera una sola entrada. Se conserva `0 3 * * *` como recuperación nocturna de turnos ya pendientes, no como una lectura forzada. Si ambas fuentes se pausan se elimina `schedule` y se conserva la actualización manual.

El intervalo de 1 a 60 días sigue calculándose con el calendario y estado publicados. No se usa `*/5` en el día del mes: eso no representa cinco días transcurridos al atravesar los meses. CNRT no se descarga diariamente por el hecho de tener un cron diario.

## Permiso necesario una sola vez

Para que un proceso modifique `.github/workflows`, el token habitual de Actions no basta. Crear un fine-grained personal access token limitado únicamente a `SanLean17/parque-movil-ftr`, con `Contents: Read and write` y `Workflows: Read and write`, y guardarlo como secreto del repositorio `FTR_SCHEDULE_TOKEN`. No requiere permisos de Google, de Secrets ni de administración de la cuenta. No reemplaza el token de la aplicación local.

El token se utiliza únicamente cuando el commit necesita modificar el archivo de calendario; no se escribe en los archivos, en la URL, en los argumentos del proceso ni en la configuración Git. La publicación utiliza la URL fija de este repositorio y nunca force-push. No se imprimen respuestas de autenticación que puedan revelar credenciales.

Sin el secreto, un cambio de horario se rechaza ANTES de leer fuentes o publicar la configuración. No se muestra como un guardado correcto de un horario que GitHub no puede programar. Las lecturas programadas, las actualizaciones manuales y los cambios que no modifican el YAML siguen usando la autorización normal de Actions. Si vence el secreto, la agenda ya guardada sigue existiendo; se necesita renovarlo para editarla.

## Líneas y fuentes

Agregar una línea y su empresa sigue utilizando la configuración central y la validación existente, incluyendo la separación del parque por línea dentro de una empresa. No hay que reescribir manualmente los lectores o el HTML. Los cambios de planilla o período conservan sus comprobaciones de acceso y formato.

## Prueba y límites

Las pruebas nuevas verifican la conversión de las 24 horas, minutos, fuentes pausadas, deduplicación de horarios, rechazo sin credencial, protección de secretos y commit conjunto de configuración/YAML. Usan claves ficticias y transporte simulado. No ejecutan lecturas reales ni prueban la autorización futura que agregue el administrador.

Cambiar el YAML corrige la forma de guardar la programación solicitada. NO demuestra que ese fuera el motivo de la ausencia anterior de eventos `schedule`, ni garantiza puntualidad de GitHub Actions. La validación de funcionamiento autónomo requiere una ejecución real con evento `schedule` y publicación confirmada. Una ejecución manual, el guardado de configuración y las pruebas no se cuentan como esa validación.
