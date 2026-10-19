# Estadísticas 04 — contrato del panel y resultado de prueba

La aplicación de prueba se entrega como HTML local completo en un paquete privado. El paquete incluye detalle de fiscalizaciones y una llave de informes: NO subirlo al repositorio público. Esta documentación no contiene dominios, internos o claves.

## Qué se implementó

`_ftr_admin/estadisticas_periodo.py` amplía el diagnóstico probado sin reemplazar el lector ni el bot de producción. Clasifica exclusivamente la columna ESTADO en Fuera de servicio, Observado, Sin novedad, Sin estado y Otro estado. No interpreta NOVEDADES.

El informe valida dos invariantes antes de ser generado:

- Registros válidos - vehículos diferentes por línea = controles adicionales.
- Fuera de servicio + Observado + Sin novedad + Sin estado + Otro estado = registros válidos.

Una tabla no identificada es desconocida, no cero. Las ausencias del parque y los cambios de interno no son bajas confirmadas ni se autocorrigen.

## Definiciones para el panel

- **Controles registrados:** filas válidas del período. Un mismo vehículo puede tener varios registros.
- **Vehículos diferentes:** cada par línea-dominio se cuenta una vez.
- **Vehículos controlados más de una vez:** cantidad de vehículos con dos o más registros dentro de su línea.
- **Controles adicionales del mismo vehículo:** suma de registros después del primero de cada par línea-dominio.

Ejemplo: un vehículo con 3 registros y otro con 2 = 2 vehículos repetidos y 3 controles adicionales. Los indicadores coinciden solamente cuando todos los repetidos tienen exactamente 2 registros. Las coincidencias exactas de fecha, dominio e interno siguen señaladas como posibles duplicados, no se eliminan.

## Resultados

Cada columna de resultado cuenta inspecciones registradas, no la situación actual de los vehículos. Parque actual se incluye como referencia y no se utiliza como denominador de los resultados históricos. Unidades fuera de servicio significa dominios diferentes con al menos un registro con ese resultado durante el período, no unidades actualmente fuera de servicio.

Se elimina la tarjeta separada y ambigua «Líneas con ese resultado». La cantidad de líneas con fuera de servicio se explica debajo de su propia tarjeta. Se agrega la tarjeta Observado y se cambia Fuera de servicio a escritura normal.

## Tablas comunes

Cobertura actual, Resultados, Repeticiones y Diagnóstico anual usan un mismo componente visual: encabezado azul en claro/pizarra en oscuro, números monoespaciados, líneas destacadas y filas alternadas sutiles. En móvil se adaptan a bloques etiquetados.

Todas incluyen Parque actual. Resultados muestra Controles registrados, Fuera de servicio, Observado, Sin novedad, Sin estado y Otro estado. Repeticiones incluye los dos indicadores distintos y Posibles duplicados exactos. La importación de informes conserva parque_publicado. Un resumen y un detalle privado deben coincidir en período, revisión GitHub y momento de lectura.

## Lectura real validada

Ejecución: https://github.com/SanLean17/parque-movil-ftr/actions/runs/39337392189
Commit ejecutado: f691f84f7af24eea94da69d9380ad5eed1c44077
Inicio: 2026-10-19T22:47:44.458681+00:00 (19:47 Argentina).

- LECTURA_COMPLETA; cero errores de carga.
- 38 pestañas y 48 líneas habilitadas reconocidas.
- 1.900 registros válidos y 1.846 pares únicos línea-dominio.
- 54 vehículos repetidos, 54 controles adicionales, 1 posible duplicado exacto adicional.
- 305 registros fuera de servicio en 46 líneas; 96 Observado en 27 líneas; 1.497 Sin novedad; 2 Sin estado; 0 Otro estado.
- Línea 2: parque comparado 55, registros 51, fuera de servicio 7, Observado 3, Sin novedad 41, Sin estado 0, Otro estado 0.
- 26 advertencias y 143 observaciones informativas, no bloqueos por errores de carga.
- 64 pruebas unitarias: 26 del lector, 21 administrativas, 17 nuevas de estadísticas. Paso CI exitoso.
- La prueba comprobó que no cambió ningún archivo de la copia del repositorio.

## Estado de integración

Main, la fuente publicada, agendas, HTML públicos y bots vigentes siguen sin modificación. El panel local incluye una copia del diagnóstico real, no solicita lecturas ni publica configuraciones desde sus botones. La lógica de lectura y estadísticas está validada; faltan el cliente local autorizado, configuración central, agendas y publicación validada. No confundir lectura completa con integración completa.
