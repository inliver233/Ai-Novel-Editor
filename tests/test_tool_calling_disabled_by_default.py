import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.ai_client import AIClient, AIClientError, AIConfig, AIProvider


class TestToolCallingGuard(unittest.TestCase):
    def test_complete_with_tools_requires_explicit_enable(self):
        config = AIConfig(provider=AIProvider.OPENAI, model="gpt-3.5-turbo")
        client = AIClient(config)

        with self.assertRaises(AIClientError) as context:
            client.complete_with_tools("hi", tools=[])

        self.assertIn("enable_tools", str(context.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

