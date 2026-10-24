import unittest
from unittest.mock import patch
from datetime import timedelta
from flask import Flask
from _ftr_app import main0631,test_outbox as fixtures
from _ftr_app.queue_runs import RunScan

class RoutesTests(unittest.TestCase):
    setUp=fixtures.OutboxTests.setUp
    tearDown=fixtures.OutboxTests.tearDown
    new_queue=fixtures.OutboxTests.new_queue
    add=fixtures.OutboxTests.add

    def test_authenticated_recovery_routes_use_existing_queue_and_never_dispatch(self):
        first=self.add();self.add('diagnostic',config=self.config)
        self.dispatch.side_effect=TimeoutError();self.queue.tick();self.now+=timedelta(minutes=6)
        self.runs.return_value=RunScan([],dict(complete=True,examined=301))
        app=Flask('queue-routes');server=main0631.server
        app.before_request(server.secure);app.register_error_handler(Exception,server.errors)
        app.view_functions.update(connect=lambda:None,submit=lambda:None,status=lambda:None)
        with patch.object(server,'app',app),patch.object(server,'VERSION',server.VERSION),patch.object(server,'DATA',self.root),patch.object(main0631,'outbox',self.queue):
            main0631.install();client=app.test_client()
            self.assertEqual(client.post('/api/orders/check',base_url=server.ORIGIN,json={'request_id':first['id']}).status_code,403)
            client.set_cookie(server.COOKIE_NAME,server.SESSION,domain='127.0.0.1')
            headers={'X-FTR-CSRF':server.CSRF,'Origin':server.ORIGIN}
            def post(path,data):return client.post('/api/orders/'+path,base_url=server.ORIGIN,headers=headers,json=data)
            response=post('check',{'request_id':first['id']});self.assertEqual(response.status_code,200)
            token=response.json['blocked']['resolution']['confirmation']
            self.assertEqual(post('resolve',{'request_id':first['id'],'confirmation':'bad'}).status_code,400)
            response=post('resolve',{'request_id':first['id'],'confirmation':token})
            self.assertEqual(response.status_code,200);self.assertTrue(response.json['paused'])
            response=post('resume',{'confirmation':response.json['confirmation']})
            self.assertEqual(response.status_code,200);self.assertFalse(response.json['paused'])
            self.dispatch.assert_called_once()
