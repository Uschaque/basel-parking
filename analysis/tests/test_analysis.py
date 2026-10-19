import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_analysis import feature_matrix, fit_ridge, make_split, predict_ridge  # noqa: E402


class ChronologyTests(unittest.TestCase):
    def test_split_has_no_overlap(self):
        stamps = pd.date_range("2026-01-01", periods=300 * 24, freq="h", tz="UTC")
        frame = pd.DataFrame({"published_utc": stamps})
        split = make_split(frame)
        train = frame[(frame.published_utc >= split.train_start) & (frame.published_utc < split.holdout_start)]
        holdout = frame[frame.published_utc >= split.holdout_start]
        self.assertLess(train.published_utc.max(), holdout.published_utc.min())
        self.assertEqual((split.cutoff - split.holdout_start).days, 56)

    def test_ridge_predictions_are_bounded_and_deterministic(self):
        stamps = pd.date_range("2026-01-01", periods=1000, freq="h", tz="UTC")
        frame = pd.DataFrame({
            "published_utc": stamps,
            "published_local": stamps.tz_convert("Europe/Zurich"),
            "total": 500,
        })
        x = feature_matrix(frame, stamps[0])
        y = 0.5 + 0.2 * np.sin(2 * np.pi * frame.published_local.dt.hour.to_numpy() / 24)
        first = fit_ridge(x, y, 1.0)
        second = fit_ridge(x, y, 1.0)
        p1 = predict_ridge(first, x)
        p2 = predict_ridge(second, x)
        self.assertTrue(np.allclose(p1, p2))
        self.assertTrue(np.all((0 <= p1) & (p1 <= 1)))


if __name__ == "__main__":
    unittest.main()
