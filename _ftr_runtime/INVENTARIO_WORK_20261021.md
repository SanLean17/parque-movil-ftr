# Inventario de partida — auditoría 21/10/2026

Base examinada: `1824da51985b54fd91b74f580fc35aa1f5922dbb`. 200 archivos versionados; respaldo `69088bd844df11865cf5f5790dd18e13b251674e`: 147 archivos. Dependencias obtenidas de imports y referencias estáticas; las llamadas dinámicas se explican en el informe. Inventario no equivale a certificación material de cada fila o función.

| Archivo | Función / alcance | Dependencias directas |
|---|---|---|
| `${GITHUB_OUTPUT}` | Legado/residuo; fuera del camino activo, conservado | — |
| `.github/workflows/actualizar_parques.yml` | Producción | `./.github/workflows/ftr_sincronizar.yml` |
| `.github/workflows/ftr_agenda_pruebas062.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.github/workflows/ftr_calendario_nativo_pruebas.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6` |
| `.github/workflows/ftr_correccion061.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.github/workflows/ftr_integracion_pruebas.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f`, `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.github/workflows/ftr_reparacion063_pruebas.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.github/workflows/ftr_respaldo064_pruebas.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.github/workflows/ftr_sincronizar.yml` | Producción | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.github/workflows/probar_planilla_anual.yml` | Workflow de pruebas o empaquetado histórico; revisar filtro de rama | `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `.gitignore` | Código o dependencia del recorrido activo | — |
| `_ftr_admin/destacados_periodo.py` | Diagnóstico/estadísticas; extend_report y completar_estadisticas activos; CLI auxiliares | `__future__`, `collections`, `datetime`, `diagnostico_administrativo`, `estadisticas_periodo`, `json`, `os`, `pathlib`, `sys`, `zoneinfo` |
| `_ftr_admin/diagnostico_administrativo.py` | Diagnóstico/estadísticas; extend_report y completar_estadisticas activos; CLI auxiliares | `__future__`, `base64`, `collections`, `cryptography.hazmat.primitives`, `cryptography.hazmat.primitives.asymmetric`, `cryptography.hazmat.primitives.ciphers.aead`, `csv`, `datetime`, `hashlib`, `io`, `json`, `os`, `pathlib`, `planilla_anual`, `re`, `sys`, `zoneinfo` |
| `_ftr_admin/diagnostico_publica.pem` | Clave pública de cifrado; no es clave privada | — |
| `_ftr_admin/estadisticas_periodo.py` | Diagnóstico/estadísticas; extend_report y completar_estadisticas activos; CLI auxiliares | `__future__`, `collections`, `datetime`, `diagnostico_administrativo`, `json`, `os`, `pathlib`, `re`, `sys`, `unicodedata`, `zoneinfo` |
| `_ftr_admin/test_admin.py` | Pruebas, sin uso como lector de producción | `base64`, `cryptography.exceptions`, `cryptography.hazmat.primitives`, `cryptography.hazmat.primitives.asymmetric`, `cryptography.hazmat.primitives.ciphers.aead`, `datetime`, `diagnostico_administrativo`, `json`, `os`, `pathlib`, `sys`, `tempfile`, `unittest`, `unittest.mock` |
| `_ftr_admin/test_destacados_periodo.py` | Pruebas, sin uso como lector de producción | `datetime`, `destacados_periodo`, `unittest` |
| `_ftr_admin/test_estadisticas_periodo.py` | Pruebas, sin uso como lector de producción | `collections`, `copy`, `datetime`, `estadisticas_periodo`, `unittest` |
| `_ftr_app/agenda_bridge.py` | Cliente local; contrato 06.3. main064/local_clock son auxiliares 06.4, no reloj de producción | `__future__`, `_ftr_runtime.agenda`, `datetime`, `pathlib`, `server`, `sys` |
| `_ftr_app/browser_smoke061.py` | Pruebas, sin uso como lector de producción | `json`, `pathlib`, `playwright.sync_api`, `re`, `subprocess`, `sys`, `tempfile`, `time`, `traceback` |
| `_ftr_app/local_clock.py` | Cliente local; contrato 06.3. main064/local_clock son auxiliares 06.4, no reloj de producción | `__future__`, `_ftr_runtime.agenda`, `_ftr_runtime.config`, `contextlib`, `datetime`, `fcntl`, `hashlib`, `json`, `msvcrt`, `os`, `pathlib`, `secrets`, `threading` |
| `_ftr_app/local_clock_ui.js` | Cliente local; contrato 06.3. main064/local_clock son auxiliares 06.4, no reloj de producción | — |
| `_ftr_app/main064.py` | Cliente local; contrato 06.3. main064/local_clock son auxiliares 06.4, no reloj de producción | `__future__`, `_ftr_runtime.config`, `agenda_bridge`, `base64`, `json`, `local_clock`, `pathlib`, `re`, `server`, `sys` |
| `_ftr_app/server.py` | Cliente local; contrato 06.3. main064/local_clock son auxiliares 06.4, no reloj de producción | `__future__`, `_ftr_runtime.config`, `base64`, `cryptography.hazmat.primitives`, `cryptography.hazmat.primitives.asymmetric`, `cryptography.hazmat.primitives.ciphers.aead`, `ctypes`, `datetime`, `flask`, `html`, `io`, `json`, `logging`, `os`, `pathlib`, `requests`, `secrets`, `sys`, `tempfile`, `threading`, `urllib.parse`, `webbrowser`, `werkzeug.exceptions`, `werkzeug.serving`, `zipfile` |
| `_ftr_app/test_agenda_bridge.py` | Pruebas, sin uso como lector de producción | `agenda_bridge`, `pathlib`, `sys`, `unittest`, `unittest.mock` |
| `_ftr_app/test_local_clock064.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime.config`, `base64`, `copy`, `datetime`, `json`, `local_clock`, `main064`, `pathlib`, `sys`, `tempfile`, `threading`, `time`, `unittest`, `unittest.mock` |
| `_ftr_app/test_server.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime.config`, `pathlib`, `server`, `sys`, `tempfile`, `unittest`, `unittest.mock` |
| `_ftr_app/test_startup061.py` | Pruebas, sin uso como lector de producción | `pathlib`, `server`, `sys`, `tempfile`, `unittest`, `unittest.mock` |
| `_ftr_config.json` | Configuración central y adaptador para consumidores | — |
| `_ftr_estado.json` | Estado operativo/manifiesto; no inventar lecturas | — |
| `_ftr_panel/AJUSTES_05.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `_ftr_panel/ESTADISTICAS_04.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `_ftr_panel/README.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `_ftr_panel/modelo_panel05.js` | Modelo y documentación del panel; sin calendario de producción | — |
| `_ftr_panel/test_modelo_panel05.cjs` | Pruebas, sin uso como lector de producción | — |
| `_ftr_pruebas/README.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `_ftr_pruebas/planilla_anual.py` | Lector anual ACTIVO, importado por runtime/admin | `__future__`, `_ftr_runtime.config`, `ast`, `collections`, `csv`, `dataclasses`, `datetime`, `google.oauth2`, `google_auth_httplib2`, `googleapiclient.discovery`, `googleapiclient.errors`, `googleapiclient.http`, `httplib2`, `io`, `json`, `os`, `pathlib`, `posixpath`, `re`, `sys`, `unicodedata`, `urllib.parse`, `xml.etree`, `zipfile`, `zoneinfo` |
| `_ftr_pruebas/requirements.txt` | Código o dependencia del recorrido activo | — |
| `_ftr_pruebas/test_exportacion.py` | Pruebas, sin uso como lector de producción | `datetime`, `planilla_anual`, `unittest` |
| `_ftr_pruebas/test_planilla_anual.py` | Pruebas, sin uso como lector de producción | `datetime`, `io`, `json`, `pathlib`, `planilla_anual`, `tempfile`, `unittest`, `zipfile` |
| `_ftr_runtime/AUDITORIA_063.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `_ftr_runtime/PROGRAMACION_NATIVA.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `_ftr_runtime/agenda.py` | Código o dependencia del recorrido activo | `__future__`, `config`, `datetime`, `zoneinfo` |
| `_ftr_runtime/config.py` | Código o dependencia del recorrido activo | `__future__`, `datetime`, `hashlib`, `json`, `pathlib`, `re`, `urllib.parse`, `zoneinfo` |
| `_ftr_runtime/native_schedule.py` | Código o dependencia del recorrido activo | `__future__`, `base64`, `config`, `datetime`, `os`, `pathlib`, `subprocess`, `zoneinfo` |
| `_ftr_runtime/test_agenda062.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime`, `_ftr_runtime.config`, `copy`, `datetime`, `pathlib`, `unittest` |
| `_ftr_runtime/test_agenda063.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime`, `_ftr_runtime.config`, `_ftr_tools`, `contextlib`, `copy`, `datetime`, `json`, `os`, `pathlib`, `tempfile`, `unittest`, `unittest.mock` |
| `_ftr_runtime/test_agenda_entry062.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime`, `_ftr_runtime.config`, `_ftr_tools`, `contextlib`, `copy`, `datetime`, `json`, `os`, `pathlib`, `tempfile`, `unittest`, `unittest.mock` |
| `_ftr_runtime/test_native_schedule.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime`, `_ftr_runtime.config`, `_ftr_tools`, `copy`, `json`, `os`, `pathlib`, `subprocess`, `tempfile`, `unittest`, `unittest.mock`, `yaml` |
| `_ftr_runtime/test_runtime.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime.config`, `_ftr_runtime.web`, `copy`, `datetime`, `json`, `pathlib`, `re`, `tempfile`, `unittest` |
| `_ftr_runtime/test_schedule_reads.py` | Pruebas, sin uso como lector de producción | `_ftr_runtime`, `_ftr_runtime.config`, `_ftr_tools`, `contextlib`, `copy`, `datetime`, `json`, `os`, `pathlib`, `tempfile`, `unittest`, `unittest.mock` |
| `_ftr_runtime/web.py` | Código o dependencia del recorrido activo | `config`, `json`, `pathlib`, `re` |
| `_ftr_runtime/worker.py` | Código o dependencia del recorrido activo | `__future__`, `_ftr_pruebas.planilla_anual`, `_ftr_runtime.config`, `_ftr_runtime.web`, `concurrent.futures`, `csv`, `datetime`, `diagnostico_administrativo`, `estadisticas_periodo`, `hashlib`, `io`, `json`, `os`, `pathlib`, `re`, `requests`, `shutil`, `subprocess`, `sys`, `tempfile`, `time` |
| `_ftr_tools/ejecutar.py` | Código o dependencia del recorrido activo | `_ftr_runtime`, `json`, `os`, `pathlib`, `re`, `subprocess`, `sys` |
| `actualizar_parques.py` | Código o dependencia del recorrido activo | `configuracion_lineas`, `csv`, `io`, `pandas`, `pathlib`, `re` |
| `cnrt/empresa_2003.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2005.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2008.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2010.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2013.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2015.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2021.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2022.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2023.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2024.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2033.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2037.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2042.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2048.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2054.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2058.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2062.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2064.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2067.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2068.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2075.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2077.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2079.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2080.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2099.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2100.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2101.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2105.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2111.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_2119.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_359.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_67.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_9085.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt/empresa_972.csv` | Exportación CNRT histórica; producción usa descargas temporales nuevas | — |
| `cnrt_debug.png` | Legado/residuo; fuera del camino activo, conservado | — |
| `configuracion_lineas.py` | Configuración central y adaptador para consumidores | `_ftr_runtime.config`, `pathlib` |
| `control_actualizacion.py` | Legado/residuo; fuera del camino activo, conservado | `datetime`, `pathlib` |
| `controlados/README.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `controlados/linea10.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea100.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea113.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea119.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea126.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea128.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea129.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea133.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea134.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea135.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea148.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea15.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea154.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea158.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea159.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea160.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea164.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea168.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea17.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea177.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea178.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea179.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea180.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea195.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea197.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea2.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea22.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea24.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea29.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea32.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea33.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea37.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea45.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea51.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea53.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea56.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea60.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea63.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea70.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea74.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea79.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea80.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea85.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea9.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea91.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea92.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea95.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `controlados/linea98.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `ftr-publica.js` | Web pública; lectura de CSV y fechas | — |
| `ftr_publicacion.json` | Estado operativo/manifiesto; no inventar lecturas | — |
| `index.html` | Web pública; lectura de CSV y fechas | `ftr-publica.js?v=6`, `https://cdn.tailwindcss.com`, `https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.3.2/papaparse.min.js`, `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css`, `https://fonts.googleapis.com`, `https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@700;800&display=swap`, `linea.html?id=${id}` |
| `leer_controlados_drive.py` | Legado/residuo; fuera del camino activo, conservado | `configuracion_lineas`, `datetime`, `google.oauth2`, `googleapiclient.discovery`, `googleapiclient.http`, `io`, `json`, `openpyxl`, `os`, `pandas`, `pathlib`, `re` |
| `linea.html` | Web pública; lectura de CSV y fechas | `ftr-publica.js?v=6`, `https://cdn.tailwindcss.com`, `https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.3.2/papaparse.min.js`, `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css`, `https://fonts.googleapis.com`, `https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@700;800&display=swap`, `https://fonts.gstatic.com`, `index.html` |
| `parques/README.md` | Documentación; referencias de versiones anteriores conservadas | — |
| `parques/linea10.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea100.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea113.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea119.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea126.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea128.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea129.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea133.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea134.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea135.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea148.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea15.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea154.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea158.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea159.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea160.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea164.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea168.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea17.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea177.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea178.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea179.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea180.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea195.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea197.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea2.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea22.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea24.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea29.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea32.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea33.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea37.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea45.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea51.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea53.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea56.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea60.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea63.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea70.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea74.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea79.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea80.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea85.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea9.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea91.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea92.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea95.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `parques/linea98.csv` | Datos publicados; lectura web y diagnóstico, preservados | — |
| `requirements.txt` | Código o dependencia del recorrido activo | — |
| `scraper.py` | Código o dependencia del recorrido activo | `configuracion_lineas`, `pathlib`, `playwright.sync_api`, `re` |
| `ultima_actualizacion.txt` | Legado/residuo; fuera del camino activo, conservado | — |
| `ultima_actualizacion_controlados.txt` | Fecha de inicio de la última lectura guardada | — |
| `ultima_actualizacion_parque.txt` | Fecha de inicio de la última lectura guardada | — |
