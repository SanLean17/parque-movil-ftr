import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import server
from _ftr_runtime.config import load,digest

class LocalSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(server,'DATA',Path(self.temp.name));self.patch.start()
        self.client=server.app.test_client();self.base=server.ORIGIN
        self.c=load(Path(__file__).resolve().parents[1]);self.headers={'Origin':self.base,'X-FTR-CSRF':server.CSRF}
    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def login(self):self.client.get('/iniciar/'+server.BOOT,base_url=self.base)
    def test_no_session(self):self.assertEqual(self.client.get('/api/status',base_url=self.base,headers=self.headers).status_code,403)
    def test_bad_host(self):self.assertEqual(self.client.get('/iniciar/'+server.BOOT,base_url='http://evil.test').status_code,403)
    def test_invalid_bootstrap(self):self.assertEqual(self.client.get('/iniciar/wrong',base_url=self.base).status_code,403)
    def test_cookie_http_only(self):
        r=self.client.get('/iniciar/'+server.BOOT,base_url=self.base);self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertIn('SameSite=Strict',r.headers['Set-Cookie'])
    def test_no_csrf(self):
        self.login();self.assertEqual(self.client.post('/api/draft',base_url=self.base,json={},headers={'Origin':self.base}).status_code,403)
    def test_foreign_origin(self):
        self.login();self.assertEqual(self.client.post('/api/draft',base_url=self.base,json={},headers={'Origin':'https://evil.test','X-FTR-CSRF':server.CSRF}).status_code,403)
    def test_local_draft_without_network(self):
        self.login()
        with patch.object(server,'api',side_effect=AssertionError('No network')):
            r=self.client.post('/api/draft',base_url=self.base,headers=self.headers,json={'config':self.c,'expected':'abc'})
        self.assertEqual(r.status_code,200);self.assertTrue((server.DATA/'borrador.json').exists())
    def test_arbitrary_action_rejected(self):
        self.login();r=self.client.post('/api/submit',base_url=self.base,headers=self.headers,json={'action':'delete_repository'})
        self.assertEqual(r.status_code,400)
    def test_stale_configuration_never_dispatched(self):
        self.login()
        with patch.object(server,'remote',return_value={'config':self.c,'digest':digest(self.c)}),patch.object(server,'last_runs',return_value=[]),patch.object(server,'api') as post:
            r=self.client.post('/api/submit',base_url=self.base,headers=self.headers,json={'action':'config','config':self.c,'expected':'old'})
        self.assertEqual(r.status_code,400);post.assert_not_called()
    def test_update_only_one_bot(self):
        self.login()
        with patch.object(server,'remote',return_value={'config':self.c,'digest':digest(self.c)}),patch.object(server,'last_runs',return_value=[]),patch.object(server,'api',return_value={}) as post:
            r=self.client.post('/api/submit',base_url=self.base,headers=self.headers,json={'action':'drive'})
        self.assertEqual(r.status_code,200)
        payload=post.call_args.args[2];self.assertEqual(payload['inputs']['action'],'drive');self.assertEqual(payload['ref'],'main')
    def test_busy_not_duplicated(self):
        self.login()
        with patch.object(server,'remote',return_value={'config':self.c,'digest':digest(self.c)}),patch.object(server,'last_runs',return_value=[{'status':'in_progress'}]),patch.object(server,'api') as post:
            r=self.client.post('/api/submit',base_url=self.base,headers=self.headers,json={'action':'all'})
        self.assertEqual(r.status_code,400);post.assert_not_called()
    def test_error_does_not_echo_secret(self):
        self.login()
        with patch.object(server,'remote',side_effect=RuntimeError('secret_value_hidden')):
            r=self.client.get('/api/status',base_url=self.base,headers=self.headers)
        self.assertEqual(r.status_code,500);self.assertNotIn('secret_value_hidden',r.text)
    def test_reset_not_delete_auth(self):
        self.login();(server.DATA/'github.dpapi').write_bytes(b'test');(server.DATA/'borrador.json').write_text('{}')
        r=self.client.post('/api/reset-draft',base_url=self.base,headers=self.headers,json={})
        self.assertEqual(r.status_code,200);self.assertFalse((server.DATA/'borrador.json').exists());self.assertTrue((server.DATA/'github.dpapi').exists())

if __name__=='__main__':unittest.main()
