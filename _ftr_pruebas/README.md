# Prueba de planilla anual — sin publicar

Esta carpeta prepara el nuevo lector de Controles FTR 2026. No reemplaza los bots de producción.

## Garantías de esta fase

- Solo lectura del archivo de Google indicado, mediante el Secret existente `GOOGLE_SERVICE_ACCOUNT_JSON` y el alcance `drive.readonly`.
- XLSX exportado en memoria; no se sube la planilla laboral al repositorio ni al artefacto.
- Los informes contienen cantidades, códigos de aviso y posiciones. No contienen dominios, responsables, direcciones, novedades ni claves.
- No escribe en `controlados/`, `parques/`, HTML, configuración activa ni archivos de actualización.
- No llama a CNRT, no ejecuta el workflow de producción y no hace commit de resultados.
- La rama de pruebas no se publica en GitHub Pages. No fusionar hasta revisar los resultados y aprobar la integración.

## Lectura

Reconoce FECHA / DOMINIO / INTERNO por nombres, no por letras de columnas. En pestañas múltiples usa la columna LÍNEA de cada fila; no adivina por interno o empresa. Ignora Tablero de Control. Continúa después de filas vacías. Acepta celdas combinadas reales, fechas Excel y texto. Selecciona el período y deduplica línea + dominio conservando la fecha más reciente.

Un registro puede estar controlado aunque su estado sea fuera de servicio: el estado no decide si fue inspeccionado. La ausencia de un dominio en el parque comparado NO prueba una baja oficial.

Tabla reconocida y vacía: cero. Tabla no reconocida o ausente: sin determinar. Los avisos requieren revisión y nunca reinician producción.

## Ejecución

El workflow `probar_planilla_anual.yml` se activa por push exclusivamente en `ftr/prueba-planilla-anual` y para los archivos de esta prueba. No tiene agenda ni usa permisos de escritura. Antes de leer Google ejecuta pruebas unitarias sin red. El informe se guarda fuera del repositorio, en el directorio temporal del runner, como un artefacto de siete días.

El resumen puede ser visible para personas con acceso al repositorio público. Por eso solo se publican métricas agregadas y posiciones de avisos, no contenido de las filas.

## Pruebas locales

`python -m unittest discover -s _ftr_pruebas -p 'test_*.py' -v`

Las pruebas usan datos ficticios y solo la biblioteca estándar de Python. Las dependencias Google se cargan únicamente en la lectura real.
