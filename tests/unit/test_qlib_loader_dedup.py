import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.datahub.loaders import qlib_bin


class TestQlibLoaderDedup(unittest.TestCase):
    def test_read_instruments_preserves_order_and_removes_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "instruments").mkdir(parents=True)
            (root / "instruments" / "sp500.txt").write_text("AAPL\nMSFT\nAAPL\nNVDA\n", encoding="utf-8")

            self.assertEqual(qlib_bin.read_instruments(str(root), "sp500"), ["AAPL", "MSFT", "NVDA"])

    def test_load_daily_bar_deduplicates_explicit_instrument_list_before_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            feature_dir = root / "features" / "aapl"
            feature_dir.mkdir(parents=True)
            for field in ["open", "high", "low", "close", "volume", "factor"]:
                (feature_dir / f"{field}.day.bin").write_bytes(np.array([0], dtype="<u4").tobytes() + np.array([10, 11], dtype="<f4").tobytes())

            with patch.object(qlib_bin, "read_calendar", lambda _provider: __import__("pandas").DatetimeIndex(["2026-05-08", "2026-05-09"])):
                out = qlib_bin.load_daily_bar(str(root), instruments=["AAPL", "AAPL"], instrument_limit=1)

            self.assertEqual(out[["trade_date", "asset_code"]].drop_duplicates().shape[0], 2)
            self.assertEqual(out.shape[0], 2)


if __name__ == "__main__":
    unittest.main()
