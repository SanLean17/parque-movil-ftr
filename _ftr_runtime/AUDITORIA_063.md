# Auditoría FTR 06.3 — GitHub y aplicación local

## Alcance

Se inventariaron los 187 archivos de `e319b5a8a918b0bc50d580e1e27e0166c598f833` y se compararon por ruta, tamaño y hash con los 147 archivos de `69088bd844df11865cf5f5790dd18e13b251674e` (versión anterior al panel). Se revisaron el camino de ejecución, todos los workflows, configuración, estado, lectores, publicación, servidor local y modelos del panel. Los 28 Python tenían sintaxis válida. Se verificó la estructura de los 130 CSV (48 parques, 48 controles y 34 exportaciones CNRT), y además la unicidad y formato de los dominios publicados y la asignación línea/empresa en los parques. No se encontraron errores estructurales en esos CSV. Esta comprobación no certifica la exactitud material de cada fiscalización.

No se revisaron otros repositorios. No se descargaron datos nuevos de Google/CNRT durante las pruebas, no se cambiaron credenciales, períodos ni horarios del usuario y no se solicitó una actualización manual para simular una automática.

## Componentes anteriores preservados

Los siguientes archivos son idénticos byte por byte a la revisión anterior: `scraper.py`, `actualizar_parques.py`, `leer_controlados_drive.py`, `control_actualizacion.py`, `configuracion_lineas.py`. El lector de carpetas anterior no se conecta de nuevo a producción: el calendario restaurado llama al lector anual actual.

El CSV publicado de la Línea 195 conserva 57 registros. Las líneas 9 y 164 tienen 65 y 67 respectivamente, separadas por su asignación, no por el total de la empresa.

## Bugs encontrados en la coordinación nueva

1. **Guardar una hora pasada descartaba el turno pendiente de ese día.** El estado real auditado tenía vigencia de horario a las 20:27, horario 17:00 y última lectura del día anterior. La comparación `slot < effective` descartaba la lectura de hoy. Se conserva ahora el turno de ese día sin recuperar días anteriores a la vigencia y sin inventar lecturas.
2. **El enfriamiento de reintentos se aplicaba también a éxitos.** Una lectura manual correcta a las 16:45 bloqueaba el turno de las 17:00 por una hora. El enfriamiento queda reservado a intentos no exitosos; los éxitos se deduplican por turno y lectura efectiva.
3. **Cambio de fuentes entre preparación y procesamiento.** Se recalculaba la agenda tras instalar dependencias: CNRT podía incorporarse al llegar su hora sin que se hubiera preparado Chromium. Se limita el procesamiento a las fuentes preparadas; las demás siguen pendientes para el siguiente chequeo.
4. **Turno satisfecho por hora de finalización.** Una lectura empezada antes del turno y terminada después podía consumirlo incorrectamente. Se marca por `read_utc`, el inicio real de la lectura.

Se agregaron 18 regresiones para estas condiciones. Ejecutadas contra el código anterior, 10 fallan. Con la corrección, las 18 pasan. Las pruebas existentes no cubrían estas condiciones.

También se corrigieron las pruebas de HTML para usar UTF-8 explícitamente en Windows. La nueva batería verifica el código de salida de cada suite: no acepta como éxito que una suite posterior pase cuando otra anterior falló.

## Entrada programada restaurada

`actualizar_parques.yml` vuelve a ser la única entrada con `on.schedule`, conservando su comprobación diaria original (`0 3 * * *`) y comprobaciones en 07, 22, 37 y 52. Llama a `ftr_sincronizar.yml` con modo `scheduled`; este último conserva las órdenes manuales del panel y el coordinador reutilizable, pero no otro calendario. La exclusión mutua permanece solamente en el coordinador llamado para evitar bloqueo entre padre e hijo y doble publicación.

El programa local 06.3 muestra ambos historiales, deduplicados: órdenes manuales/configuración y eventos del calendario. Con ello un proceso automático del workflow original no queda invisible en el panel. No se cambian sus credenciales ni su interfaz.

## Límite de la conclusión

Estos bugs son reproducibles y se corrigen, pero NO explican por sí solos la ausencia de eventos `schedule` en GitHub. El estado previo mostraba ejecuciones automáticas muy espaciadas y ninguna posterior a las 16:34 al comenzar la revisión. Restituir el workflow original es una medida de recuperación del disparador; requiere comprobar un evento programado real. Un resultado verde de tests, una compilación o un guardado de configuración no se presenta como actualización de fuentes.

Las pruebas antiguas estaban limitadas a ramas de desarrollo; no hay evidencia de que causaran un conflicto de calendario. Se conservan deshabilitadas. Los módulos de lectura bajo `_ftr_pruebas` se importan en producción y no deben borrarse por el nombre de la carpeta. El archivo residual `${GITHUB_OUTPUT}` no es un disparador activo y no se elimina como supuesto remedio.

## Seguridad de activación

La configuración, los CSV, las fechas de lectura y los HTML públicos no forman parte del diff de esta reparación. El workflow original debe habilitarse después de fusionar este cambio; hacerlo antes ejecutaría su antigua acción manual `all`. La activación solo habilita workflows, sin llamadas `dispatches` ni consultas a Google/CNRT. La posterior actualización solo cuenta como prueba si su evento es `schedule` y confirma lectura y publicación reales.
