import unittest

from src.agents.custom_doc_agent import CustomDocumentAgent
from src.data_providers.realtime_data_manager import RealtimeDataManager
from src.main import CONFIG_DIR
from src.utils.config import load_config_dir


class CustomDocumentAgentTest(unittest.TestCase):
    def setUp(self):
        self.configs = load_config_dir(CONFIG_DIR)
        self.manager = RealtimeDataManager(CONFIG_DIR)
        self.agent = CustomDocumentAgent(config_dir=CONFIG_DIR, configs=self.configs)

    def context(self, ticker):
        data = self.manager.refresh_universe(tickers=[ticker], realtime=True)
        return data["records"][0]

    def test_detects_yyang_eum_yyang_pattern_1(self):
        result = self.agent.evaluate(self.context("010120"))
        self.assertEqual(result["matched_pattern"], "pattern_1")

    def test_detects_yyang_eum_yyang_pattern_2(self):
        result = self.agent.evaluate(self.context("042700"))
        self.assertEqual(result["matched_pattern"], "pattern_2")

    def test_detects_yyang_eum_yyang_pattern_3(self):
        result = self.agent.evaluate(self.context("247540"))
        self.assertEqual(result["matched_pattern"], "pattern_3")

    def test_converts_pdf_rules_to_structured_rules(self):
        structured = self.agent.structured_rules()
        self.assertEqual(structured["strategy_doc"], "yyang_eum_yyang")
        self.assertIn("pattern_1", structured["patterns"])
        self.assertEqual(structured["patterns"]["pattern_1"]["bearish_volume_max_ratio_to_prev_bullish"], 0.60)


if __name__ == "__main__":
    unittest.main()
