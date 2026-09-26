import unittest
import ai.client
import ai.analyst
import inspect

class TestAIMaxTokens(unittest.TestCase):
    def test_client_payload_has_max_tokens(self):
        source = inspect.getsource(ai.client.BettingAI.analyze_event_context)
        self.assertIn('"max_tokens": 800', source)

    def test_analyst_payload_has_max_tokens(self):
        source = inspect.getsource(ai.analyst.ValueBetAnalyst.analyze)
        self.assertIn('"max_tokens": 800', source)

if __name__ == "__main__":
    unittest.main()
