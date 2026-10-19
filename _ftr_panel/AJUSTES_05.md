# Panel local 05 — ajustes solicitados

Entrega privada completa en ZIP. No publicar el HTML con datos ni la llave privada de informes en este repositorio.

## Interfaz

- Encabezados literales: Incidencias (categoría Calidad de la información), Estadísticas, Resumen, Actualizaciones, Planilla y período, Líneas habilitadas, Revisar y publicar, Conexiones y Diagnóstico anual.
- Copiar referencia incluye fecha, línea, dominio original, interno, pestaña, fila/celda, motivo y Posible solución. Un candidato del mismo interno es una referencia para verificar, no una corrección confirmada. Con varios candidatos se muestran todos; sin candidato no se inventa una patente.
- Resultados registrados reúne seis indicadores globales: controles registrados, vehículos únicos, vehículos controlados más de una vez, fuera de servicio (rojo), observado (celeste), sin novedad (verde). Se quitaron de la interfaz el contador de adicionales, su explicación larga y la tarjeta de cantidad de líneas por resultado.
- Resultados no muestra Otro estado. Sin estado permanece. Si el informe tiene estados no reconocidos, se avisa sin reclasificarlos silenciosamente.
- Repeticiones no muestra Controles adicionales ni Posibles duplicados exactos; los cálculos internos y los datos originales no se borran.
- Destacados: línea con más fuera de servicio, más observados, más controles; unidades con más controles, con dominio e interno del último registro disponible. Se conservan todos los empates. Una unidad es un par línea-dominio, no una línea completa.
- Resumen: Planilla anual FTR y Parque móvil como títulos equivalentes; Consulta CNRT como categoría pequeña. Horarios expresados sin repetir el sufijo Argentina. La zona de cálculo no cambia.
- Guardar planilla en este equipo y Descargar copia de configuración describen acciones LOCALES. Comprobar enlace solo valida su formato, no permisos o contenido.

## Cálculos

El modelo `modelo_panel05.js` se incrusta en el HTML privado. Recalcula destacados a partir de cada informe cargado, sin acceder a red. Hay 22 pruebas locales de referencias, empates y textos.

Se agregó `_ftr_admin/destacados_periodo.py` y 14 pruebas para una futura integración del cálculo de fechas distintas de visita y líderes por unidad. El workflow conserva `estadisticas_periodo.py` como entrada: no afirmar que el nuevo punto de entrada esté activo. Los tres líderes por línea y líderes por unidad que muestra el panel se obtienen del informe administrativo ya disponible. No se calcula una cantidad de operativos desde filas de vehículos.

## Lectura real revisada

Ejecución: https://github.com/SanLean17/parque-movil-ftr/actions/runs/39342172033
Revisión: b71ad7674998a5b3179a32e8e04526421298606e
Inicio: 2026-10-19T23:32:24.944113+00:00 (20:32 Argentina).
Resultado: LECTURA_COMPLETA / workflow success; 1.900 registros, 1.846 pares únicos, 54 vehículos repetidos. Sin errores de carga.

Derivados del resumen de esa lectura:
- Línea 177: 18 registros fuera de servicio (máximo).
- Línea 160: 11 registros observados (máximo).
- Línea 180: 70 registros válidos (máximo).
- 54 unidades empatadas con 2 controles cada una; sus identificadores solo se muestran en el paquete privado.

## Línea 168

Ya figura como 168:2105 en `configuracion_lineas.py` de main (revisión 69088bd844df11865cf5f5790dd18e13b251674e). No fue inventada en el panel. Falta en la lista estática `const lineas` de index.html. Este turno no modifica main ni el listado público. La integración de configuración central deberá impedir estas divergencias.

## Estado real y pruebas

La publicación, el cambio de fuente, las agendas y el alta remota desde el panel siguen pendientes de integración. Guardar y exportar no envían órdenes a GitHub. No se tocaron bots de producción, CSV, fechas o HTML públicos.

El HTML se verificó en Chromium renderizando el contenido en memoria: 9 pantallas a 1440, 1024, 768 y 390 px, sin errores JavaScript ni overflow horizontal; claro/oscuro; columnas solicitadas, búsquedas y enlaces del menú. Se comprobaron guardado y portapapeles con dobles controlados y el contenido exportado sin claves. No equivale a probar un ejecutable Windows, persistencia real file:// ni descarga en el navegador del usuario. La navegación local fue restringida por el entorno de pruebas; no se cambiaron políticas del navegador.
