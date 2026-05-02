import json
import unittest

from src.main import parse_args, run_pipeline
from src.models.schemas import ProviderEnvelope


class SchemaValidationTest(unittest.TestCase):
    def test_provider_envelope_has_required_fields(self):
        envelope = ProviderEnvelope(
            source="test",
            fetched_at_kst="2026-05-02T10:00:00+09:00",
            is_realtime=True,
            is_stale=False,
            data={"x": 1},
        ).to_dict()
        self.assertEqual(set(["source", "fetched_at_kst", "is_realtime", "is_stale", "data"]).intersection(envelope), {"source", "fetched_at_kst", "is_realtime", "is_stale", "data"})

    def test_end_to_end_mock_run_outputs_report_and_json(self):
        args = parse_args(["--universe", "kospi_kosdaq", "--top-n", "3", "--realtime"])
        result = run_pipeline(args)
        result_dict = result.to_dict()
        self.assertIn("recommendations", result_dict)
        self.assertGreaterEqual(len(result_dict["recommendations"]), 1)
        self.assertIn("# Multi-Agent Stock Picker Report", result.report)
        json.dumps(result_dict, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
