import unittest
from unittest.mock import patch
from _ftr_app import test_outbox as fixtures
from _ftr_app import main0631
from _ftr_runtime import dictionary_rules as rules

class StatisticsOutboxTests(unittest.TestCase):
    setUp=fixtures.OutboxTests.setUp
    tearDown=fixtures.OutboxTests.tearDown
    new_queue=fixtures.OutboxTests.new_queue
    row=fixtures.OutboxTests.row
    found=fixtures.OutboxTests.found

    def command(self):
        return dict(expected_dictionary=rules.digest(rules.EMPTY),reglas=[dict(expresion='X12',categoria='direccion',componente='barra_larga',habilitada=True)])

    def test_dictionary_order_persists_and_only_uses_administrative_workflow(self):
        row=self.queue.enqueue(dict(action='dictionary-save',statistical=self.command()),self.remote)
        self.queue=self.new_queue();self.queue.tick();self.queue.tick()
        self.dispatch.assert_called_once()
        with patch.object(main0631.server,'api') as api:main0631.dispatch(self.row())
        self.assertEqual(api.call_args.args[:2],('POST','actions/workflows/ftr_estadisticas_admin.yml/dispatches'))
        self.assertNotIn('config_json',api.call_args.args[2]['inputs'])
        self.found(row,effect='dictionary');self.queue.tick()
        self.assertEqual(self.row()['status'],'completed')

    def test_ambiguous_duplicate_is_rejected_before_any_dispatch(self):
        payload=self.command();payload['reglas']*=2
        with self.assertRaises(ValueError):self.queue.enqueue(dict(action='dictionary-save',statistical=payload),self.remote)
        self.queue.tick();self.dispatch.assert_not_called()

    def test_history_requires_explicit_partial_flag_and_uses_own_workflow(self):
        payload=dict(period=2025,sheetUrl='FICTITIOUS_HISTORY_1234567',allow_partial=False)
        row=self.queue.enqueue(dict(action='history-import',statistical=payload),self.remote)
        with patch.object(main0631.server,'api') as api:main0631.dispatch(self.row())
        self.assertEqual(api.call_args.args[1],'actions/workflows/ftr_estadisticas_admin.yml/dispatches')
        self.assertFalse(self.row()['statistical']['allow_partial'])
        self.queue.tick();self.found(row,effect='historical');self.queue.tick()
        self.assertEqual(self.row()['status'],'completed')

if __name__=='__main__':unittest.main()
