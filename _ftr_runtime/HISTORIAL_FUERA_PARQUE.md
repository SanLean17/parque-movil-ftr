# Controlados fuera del parque móvil — Administración 06.3.2

La vista CONTROLADOS conserva la tabla actual y agrega debajo las unidades del período cuyo dominio no está en el parque de la misma línea. La comparación no identifica vehículos por su interno. TOTAL, CONTROLADOS, PENDIENTES, cobertura y copias conservan su cálculo sobre el parque actual. La portada y su fecha de última visita no se modifican.

## Información y límites

Se reutilizan `controlados/lineaN.csv`, `parques/lineaN.csv`, el manifiesto de publicación y las fechas de lectura ya guardadas. En los CSV actuales hay una última fiscalización por dominio; no contienen todos los controles anteriores. No se infieren bajas, reemplazos, transferencias ni fechas de primera ausencia. Los datos faltantes se indican como “Información no disponible”. Las coincidencias de interno son referencias, incluso si hay varios dominios posibles.

La próxima lectura automática válida generará `historial/lineaN.json` con los controles válidos disponibles en esa planilla anual. No agrega otra consulta: utiliza las filas ya leídas. Publica solamente dominio, interno, fecha de fiscalización y procedencia de lectura, sin novedades, estados, pestañas ni ubicación privada de celdas. Cada archivo queda vinculado al período, línea y huella del CSV; el manifiesto verifica sus bytes. Un historial incompatible se descarta y se muestran los últimos controles del CSV con una aclaración.

Las revisiones anteriores permanecen en Git. La proyección actual corresponde a la fuente y período configurados: no suma filas eliminadas de la fuente ni mezcla años. Una descarga CNRT no borra el historial. Si un vehículo reaparece en el parque, deja de mostrarse fuera de él sin eliminar sus controles guardados. Una línea desactivada conserva sus archivos.

El administrador reconstruye el indicador `no_en_parque` con las incidencias privadas NO_EN_PARQUE del mismo informe: período, revisión y fecha deben coincidir. Muestra los controles y las referencias de ese parque comparado. Si el detalle no está abierto, es incompatible o no reconstruye el número del indicador, informa que el detalle no está disponible. Una publicación posterior puede tener otro parque; no se mezcla con un informe antiguo.

## Caso comprobado con los archivos de 2dc5349

Línea 154: 9 vehículos actuales, 0 controlados, 9 pendientes; 5 fuera del parque. Última visita: 12/05/2026.

| Dominio | Interno | Última fiscalización |
|---|---|---|
| NNS297 | 94 | 20/01/2026 |
| NWS705 | 95 | 20/01/2026 |
| NWS706 | 87 | 20/03/2026 |
| OTK168 | 90 | 20/03/2026 |
| OTK173 | 86 | 12/05/2026 |

El interno 95 está asociado a AC992HM en el parque publicado. No demuestra un reemplazo. Esta lista es evidencia de validación, no datos escritos en la interfaz.

## Archivos

- Web: `linea.html`, `ftr-historial.js`, `ftr-historial-publico.js`, `ftr_publicacion.json`.
- Actualización existente: `_ftr_runtime/history.py`, `_ftr_runtime/worker.py`, `_ftr_tools/manifest_from_git.py`.
- Windows: `_ftr_app/panel.html`, `panel-history.js`, `server.py`, `main0631.py`, `LEEME_0631.txt`; compilación y empaquetado en `_ftr_tools/package_client.py` y `check_client_build.py`. Se conservan los nombres internos del arranque 06.3.1; la versión entregada es 06.3.2.
- Verificación: `_ftr_runtime/test_history.cjs`, `test_history.py`, `test_config_transaction.py`, `browser_history.py`, `browser_public_smoke.py`, `_ftr_app/test_panel_resources.py`, `_ftr_tools/history_browser_checks.py`, `check_panel.py`, `.github/workflows/ftr_auditoria_ci.yml`.

## Verificación y entrega

Pruebas con archivos conservados y casos ficticios: actuales e históricos simultáneos; sin históricos; repetidos; internos ambiguos; reaparición; parque válido vacío; datos incompletos; historia incompatible; coincidencia entre web y administrador; 390 y 1280 píxeles; ambos temas; búsqueda; copias y conteos. El administrador conserva los bloques CSS originales, verificados por su huella. CI prueba Linux y Windows y arranca el ejecutable compilado con datos temporales, sin órdenes reales.

El paquete estable 06.3.2 reúne las reparaciones previas y esta función. Incluye programa, panel, puente, los dos archivos de historial, instrucciones, versión y comprobantes de integridad. Deben extraerse todos juntos. Conserva la ubicación local de conexión, informes, preferencias, borrador y cola; no distribuye credenciales ni informes privados.

Este desarrollo no ejecutó manualmente Drive, CNRT ni Actualizar todo. No cambió la agenda, frecuencias, planilla, período, CSV reales ni sus fechas de lectura. Las pruebas simuladas no demuestran que se haya ejecutado el turno automático real de las 17:00. El estado de publicación y el paquete final se verifican después de integrar la PR.
