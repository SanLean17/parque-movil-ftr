import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import server

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.resource=patch.object(server,'RESOURCE',self.root);self.resource.start()
        self.data=patch.object(server,'DATA',self.root);self.data.start()
        self.client=server.app.test_client();self.base=server.ORIGIN
    def tearDown(self):
        self.data.stop();self.resource.stop();self.tmp.cleanup()
    def template(self):
        (self.root/'panel.html').write_text('<html><body>FTR __FTR_CSRF__</body></html>',encoding='utf-8')
    def test_missing_template_has_extraction_instruction(self):
        with self.assertRaisesRegex(ValueError,'Extraer todo'):server.check_resources()
    def test_incompatible_template_not_opened(self):
        (self.root/'panel.html').write_text('<html>Otra versión</html>',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'sin mezclar versiones'):server.check_resources()
    def test_valid_template(self):
        self.template();server.check_resources()
    def test_bootstrap_redirects_and_serves_full_html(self):
        self.template();r=self.client.get('/iniciar/'+server.BOOT,base_url=self.base,follow_redirects=True)
        self.assertEqual(r.status_code,200);self.assertNotIn('__FTR_CSRF__',r.text);self.assertIn(server.CSRF,r.text)
    def test_cookie_unique_to_instance(self):
        r=self.client.get('/iniciar/'+server.BOOT,base_url=self.base)
        self.assertIn(server.COOKIE_NAME+'=',r.headers['Set-Cookie']);self.assertNotEqual(server.COOKIE_NAME,'ftr')
    def test_old_bootstrap_explains_restart_in_html(self):
        r=self.client.get('/iniciar/old',base_url=self.base,headers={'Accept':'text/html'})
        self.assertEqual(r.status_code,403);self.assertIn('carpeta extra',r.text)
        self.assertNotIn(server.BOOT,r.text);self.assertNotIn(server.SESSION,r.text)
    def test_api_errors_stay_json(self):
        r=self.client.get('/api/bootstrap',base_url=self.base)
        self.assertEqual(r.status_code,403);self.assertTrue(r.is_json);self.assertEqual(r.json['code'],403)
    def test_cross_site_bootstrap_rejected(self):
        r=self.client.get('/iniciar/'+server.BOOT,base_url=self.base,headers={'Sec-Fetch-Site':'cross-site'})
        self.assertEqual(r.status_code,403)
    def test_foreign_origin_bootstrap_rejected(self):
        r=self.client.get('/iniciar/'+server.BOOT,base_url=self.base,headers={'Origin':'https://other.test'})
        self.assertEqual(r.status_code,403)
    def test_unicode_input_does_not_crash(self):
        self.assertFalse(server.matches('ñ','valid'));self.assertFalse(server.matches(None,'valid'))
    def test_live_local_http(self):
        self.template();old_port,old_origin=server.PORT,server.ORIGIN
        srv,thread=server.local_server()
        try:
            self.assertEqual(srv.server_address[0],'127.0.0.1')
            self.assertGreater(server.PORT,0)
            with patch.object(server,'api',side_effect=AssertionError('No GitHub')):
                server.verify_local_http()
        finally:
            srv.shutdown();srv.server_close();thread.join(timeout=3)
            server.PORT,server.ORIGIN=old_port,old_origin
    def test_http_errors_not_all_reported_as_authorization(self):
        self.client.get('/iniciar/'+server.BOOT,base_url=self.base)
        r=self.client.get('/not-a-screen',base_url=self.base)
        self.assertEqual(r.status_code,404);self.assertIn('pantalla',r.json['error'])

if __name__=='__main__':unittest.main()
