import unittest
from datetime import datetime, timedelta

from src.data_providers.realtime_data_manager import RealtimeDataManager
from src.main import CONFIG_DIR
from src.models.schemas import ProviderEnvelope
from src.utils.market_time import KST, iso_kst


class RealtimeRefreshTest(unittest.TestCase):
    def test_market_open_data_stale_after_configured_minutes(self):
        manager = RealtimeDataManager(CONFIG_DIR)
        current_time = datetime(2026, 5, 4, 10, 0, tzinfo=KST)
        envelope = ProviderEnvelope(
            source="test",
            fetched_at_kst=iso_kst(current_time - timedelta(minutes=20)),
            is_realtime=True,
            is_stale=False,
            data={},
        )
        self.assertTrue(manager.is_stale(envelope, current_time=current_time))

    def test_market_closed_data_stale_after_configured_hours(self):
        manager = RealtimeDataManager(CONFIG_DIR)
        current_time = datetime(2026, 5, 2, 10, 0, tzinfo=KST)
        envelope = ProviderEnvelope(
            source="test",
            fetched_at_kst=iso_kst(current_time - timedelta(hours=25)),
            is_realtime=False,
            is_stale=False,
            data={},
        )
        self.assertTrue(manager.is_stale(envelope, current_time=current_time))


if __name__ == "__main__":
    unittest.main()
