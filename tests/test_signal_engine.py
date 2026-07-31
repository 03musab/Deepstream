"""Unit tests for the Deepstream signal engine."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from deepstream import config
from deepstream.signal_engine import (
    _grade_confidence,
    compute_signal_for_pair,
    summarize,
)
from deepstream.track_record import _simulate_trade


class TestConfidence(unittest.TestCase):
    def test_grades(self):
        self.assertEqual(_grade_confidence(0.95), "HIGH")
        self.assertEqual(_grade_confidence(0.7), "HIGH")
        self.assertEqual(_grade_confidence(0.5), "MEDIUM")
        self.assertEqual(_grade_confidence(0.25), "LOW")
        self.assertEqual(_grade_confidence(0.1), "NOISE")
        self.assertEqual(_grade_confidence(0.0), "NOISE")

    def test_negative_r_uses_absolute_value(self):
        self.assertEqual(_grade_confidence(-0.8), "HIGH")
        self.assertEqual(_grade_confidence(-0.3), "LOW")


class TestSimulateTrade(unittest.TestCase):
    def setUp(self):
        # Build a simple price series: 100, then rising to target territory.
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        self.df_rise = pd.DataFrame(
            {"Price": np.linspace(100.0, 112.0, 30)}, index=idx
        )
        self.df_fall = pd.DataFrame(
            {"Price": np.linspace(100.0, 90.0, 30)}, index=idx
        )

    def test_long_win(self):
        # target = 100 * 1.08 = 108, stop = 95. Rising series hits target.
        outcome, ret, days = _simulate_trade(
            self.df_rise, 0, "LONG", 100.0, 95.0, 108.0, 30
        )
        self.assertEqual(outcome, "WIN")
        self.assertGreater(ret, 0)

    def test_long_loss(self):
        outcome, ret, days = _simulate_trade(
            self.df_fall, 0, "LONG", 100.0, 95.0, 108.0, 30
        )
        self.assertEqual(outcome, "LOSS")
        self.assertLess(ret, 0)

    def test_short_win(self):
        # Short wins when price falls: target = 92, stop = 105.
        outcome, ret, days = _simulate_trade(
            self.df_fall, 0, "SHORT", 100.0, 105.0, 92.0, 30
        )
        self.assertEqual(outcome, "WIN")
        self.assertGreater(ret, 0)


class TestSignalEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point config at a temp data dir so tests never read real data.
        cls._tmp = tempfile.TemporaryDirectory()
        cls._orig_data_dir = config.DATA_DIR
        config.DATA_DIR = Path(cls._tmp.name)

        # Create synthetic pair-2 data: chlorophyll down -> tuna up (negative corr).
        n = 500
        idx = pd.date_range("2021-01-01", periods=n, freq="D")
        rng = np.random.default_rng(7)
        chlo = 0.5 + 0.05 * np.sin(np.arange(n) / 40.0) + rng.normal(0, 0.01, n)
        tuna = 12.0 - 6.0 * (chlo - 0.5) + rng.normal(0, 0.05, n)
        pd.DataFrame({"Date": idx, "Chlorophyll": chlo}).to_csv(
            config.DATA_DIR / "chlorophyll_processed.csv", index=False
        )
        pd.DataFrame({"Date": idx, "Tuna_Price": tuna}).to_csv(
            config.DATA_DIR / "tuna_processed.csv", index=False
        )

        cls._orig_param_file = config.PARAM_FILE
        config.PARAM_FILE = Path(cls._tmp.name) / "params.json"
        config.PARAM_FILE.write_text(json.dumps({
            "test_2": {"ocean_window": 10, "price_window": 10, "optimal_lag": 10, "max_correlation": -0.9}
        }))

    @classmethod
    def tearDownClass(cls):
        config.DATA_DIR = cls._orig_data_dir
        config.PARAM_FILE = cls._orig_param_file
        cls._tmp.cleanup()

    def test_signal_for_strong_pair(self):
        params = {"test_2": {"optimal_lag": 10}}
        sig = compute_signal_for_pair(2, params)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.status, "ACTIVE")
        self.assertIn(sig.confidence, ("HIGH", "MEDIUM"))
        self.assertIn(sig.direction, ("LONG", "SHORT"))
        self.assertIsNotNone(sig.entry)
        self.assertIsNotNone(sig.stop_loss)
        self.assertIsNotNone(sig.take_profit)

    def test_summary(self):
        from deepstream.signal_engine import Signal
        sigs = [
            Signal(1, "a", "LONG", "HIGH", 0.8, 10, 100.0, 95.0, 108.0, status="ACTIVE"),
            Signal(2, "b", "SHORT", "MEDIUM", 0.5, 10, 100.0, 95.0, 108.0, status="ACTIVE"),
            Signal(3, "c", "NONE", "NOISE", 0.1, 10, status="NO_TRADE"),
        ]
        s = summarize(sigs)
        self.assertEqual(s["active"], 2)
        self.assertEqual(s["high_confidence"], 1)
        self.assertEqual(s["medium_confidence"], 1)
        self.assertEqual(s["total"], 3)


if __name__ == "__main__":
    unittest.main()
