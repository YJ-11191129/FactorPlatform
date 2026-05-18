import unittest

import pandas as pd

from app.factors.base import BaseFactor


class TestFactorPostCheck(unittest.TestCase):
    def test_missing_columns(self) -> None:
        df = pd.DataFrame([{"trade_date": "2024-01-01", "asset_code": "A"}])
        with self.assertRaises(ValueError):
            BaseFactor.post_check(df)

    def test_duplicated_keys(self) -> None:
        df = pd.DataFrame(
            [
                {"trade_date": "2024-01-01", "asset_code": "A", "factor_value": 1.0},
                {"trade_date": "2024-01-01", "asset_code": "A", "factor_value": 2.0},
            ]
        )
        with self.assertRaises(ValueError):
            BaseFactor.post_check(df)

    def test_all_na(self) -> None:
        df = pd.DataFrame(
            [
                {"trade_date": "2024-01-01", "asset_code": "A", "factor_value": None},
                {"trade_date": "2024-01-02", "asset_code": "A", "factor_value": None},
            ]
        )
        with self.assertRaises(ValueError):
            BaseFactor.post_check(df)

    def test_ok(self) -> None:
        df = pd.DataFrame(
            [
                {"trade_date": "2024-01-01", "asset_code": "A", "factor_value": 1.0},
                {"trade_date": "2024-01-02", "asset_code": "A", "factor_value": 2.0},
            ]
        )
        out = BaseFactor.post_check(df)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()

