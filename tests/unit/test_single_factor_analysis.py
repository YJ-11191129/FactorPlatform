import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.services.analysis_service import run_single_factor_analysis


class TestSingleFactorAnalysis(unittest.TestCase):
    def test_run_single_factor_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            close_path = td_path / "close.parquet"
            dates = pd.date_range("2024-01-01", periods=30, freq="B")
            rows = []
            for code, base in [("A", 100.0), ("B", 120.0), ("C", 80.0), ("D", 60.0), ("E", 90.0), ("F", 110.0)]:
                px = base + (pd.Series(range(len(dates))) * 0.1).values
                for d, c in zip(dates, px):
                    rows.append({"date": d.date(), "wind_code": code, "close": float(c)})
            pd.DataFrame(rows).to_parquet(close_path, index=False)

            os.environ["FACTOR_PLATFORM_REAL_OHLCV_PATH"] = str(close_path)

            calc_batch_id = "ut_calc_batch_1"
            run_dir = Path(__file__).resolve().parents[2] / "data" / "exports" / "factor_library" / "runs" / calc_batch_id
            if run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(parents=True, exist_ok=True)
            fv_path = run_dir / "factor_values.parquet"
            fv_rows = []
            for d in dates[:-1]:
                for code in ["A", "B", "C", "D", "E", "F"]:
                    fv_rows.append(
                        {
                            "trade_date": d.date(),
                            "asset_code": code,
                            "wind_code": code,
                            "factor_name": "UT_FACTOR",
                            "factor_version": "V1",
                            "raw_value": 1.0,
                            "winsorized_value": 1.0,
                            "zscore_value": float(ord(code[0])),
                            "neutralized_value": float(ord(code[0])),
                            "universe_name": "UT",
                            "calc_batch_id": calc_batch_id,
                            "computed_at": "2024-01-01T00:00:00Z",
                        }
                    )
            pd.DataFrame(fv_rows).to_parquet(fv_path, index=False)

            out = run_single_factor_analysis(calc_batch_id=calc_batch_id, horizon=1, quantiles=3, value_col="neutralized_value")
            self.assertIn("analysis_id", out)
            self.assertIn("summary", out)
            self.assertEqual(out["summary"]["calc_batch_id"], calc_batch_id)


if __name__ == "__main__":
    unittest.main()

