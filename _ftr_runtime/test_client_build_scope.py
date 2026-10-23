import unittest
from _ftr_tools.client_build_scope import needs_package


class ClientBuildScopeTests(unittest.TestCase):
    def test_runtime_only_keeps_windows_release(self):
        self.assertFalse(needs_package(['_ftr_runtime/anomalies.py','_ftr_diccionario.json',
            '_ftr_tools/client_build_scope.py','.github/workflows/ftr_auditoria_ci.yml']))

    def test_actual_client_changes_keep_package_checks(self):
        for path in ('_ftr_app/server.py','_ftr_app/main0631.py','_ftr_app/panel.html',
                     '_ftr_panel/style.css','_ftr_tools/package_client.py','_ftr_tools/check_client_build.py'):
            with self.subTest(path=path):self.assertTrue(needs_package([path]))
