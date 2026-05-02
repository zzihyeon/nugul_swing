import unittest

from src.agents.rs_agent import RSAgent
from src.data_providers.realtime_data_manager import RealtimeDataManager
from src.main import CONFIG_DIR
from src.utils.config import load_config_dir


class RSAgentTest(unittest.TestCase):
    def test_rs_rank_applied_first(self):
        manager = RealtimeDataManager(CONFIG_DIR)
        data = manager.refresh_universe(tickers=["000660", "005930"], realtime=True)
        results = RSAgent(configs=load_config_dir(CONFIG_DIR)).evaluate_many(data["records"])
        self.assertEqual(results[0]["ticker"], "000660")
        self.assertEqual(results[0]["rs_rank"], 1)
        self.assertGreater(results[0]["score"], results[1]["score"])


if __name__ == "__main__":
    unittest.main()
