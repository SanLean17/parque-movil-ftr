# Panel administrativo FTR — prueba 03

La interfaz local entregada como ZIP agrega Incidencias y Estadísticas al sistema UX aprobado. No es todavía un cliente autorizado para publicar configuraciones ni ejecutar workflows desde la computadora. La integración con producción permanece pendiente.

## Incidencias

- Errores: fecha inválida/futura, dominio inválido o fila sin línea.
- Advertencias: interno ausente o discrepancia de línea/interno que requiere verificación.
- Información: dominio no encontrado en el parque comparado, línea no habilitada y registro de otro período.
- Detalle privado: fecha del control, fecha de detección, línea, dominio tal como se cargó, interno, pestaña, fila y celda.
- Se muestran TODOS los candidatos del mismo interno en la MISMA línea. Son referencias del parque comparado, no correcciones ni prueba de la asignación histórica.
- No se cambia automáticamente una Ñ por L ni se inventa una baja oficial.

## Estadísticas

Registros válidos, unidades únicas por línea, coincidencias con parque, pendientes y cobertura del parque comparado, controles adicionales sobre unidades repetidas, cantidad de unidades repetidas y posibles duplicados exactos.

Los resultados FUERA DE SERVICIO y SIN NOVEDAD provienen exclusivamente de la columna ESTADO. Otros valores se contabilizan como sin clasificar. No se leen ni se infieren fallas mecánicas de NOVEDADES.

77 controles sobre 70 dominios implican 7 controles adicionales, pero no necesariamente 7 vehículos repetidos.

## Fuente y permisos

La ayuda debajo del enlace recuerda compartir cada nueva planilla con el correo completo del bot como Lector, salvo que ya disponga de acceso heredado. Incluye copiar correo. Solo se extrae client_email para ese recordatorio; ninguna clave de Google se entrega al panel.

## Privacidad

La prueba conserva en GitHub solamente un resumen agregado y el detalle administrativo cifrado. El repositorio incluye únicamente la clave PÚBLICA de informes. La clave privada de informes y la copia local legible de incidencias se entregan al administrador fuera de GitHub. No publicar ese ZIP o HTML.

El ZIP no contiene la credencial de Google ni un token GitHub. Cualquier persona con el paquete privado podría leer sus diagnósticos, por lo que debe guardarse en un lugar privado.

## Prueba real revisada

Ejecución 39330784771, revisión 869620592c2c0334bb0fda0dd9438882ca1edfa6.

- 47 pruebas unitarias pasaron (26 del lector + 21 administrativas).
- 38 pestañas; 48 líneas habilitadas identificadas.
- 1.898 registros válidos; 1.844 unidades únicas por línea.
- 54 controles adicionales y 54 unidades repetidas; 1 posible duplicado exacto adicional.
- 305 registros FUERA DE SERVICIO en 46 líneas.
- Persisten 2 dominios para revisar: línea 80, pestaña 18, celda C6; línea 85, pestaña 19, celda C24.
- 7 registros de línea 75 no habilitada y 1 de otro período: informativos, no bajas confirmadas.

El código 2 del diagnóstico significa datos para revisar; los permisos de Google funcionaron. No se modificó la planilla ni se ejecutó CNRT. La verificación de archivos del repositorio fue satisfactoria.

No fusionar esta rama como si activara el nuevo bot. Aún falta integrar configuración central, agenda, cliente local autorizado, publicación validada y recuperación ante fallos, sin sustituir a ciegas el sistema operativo.
