import unittest

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from peopleanalytics.analyzers import (BaseAnalyzer, EconometricAnalyzer, KpiAnalyzer,
                                       ReviewerAnalyzer, SegmentationAnalyzer, TrendAnalyzer,
                                       ols_cluster)
from peopleanalytics.exceptions import ModelError
from peopleanalytics.preprocessing import Preprocessor
from tests.helpers import make_raw


class AnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = Preprocessor().transform(make_raw(n_writers=24, per_writer=30))

    def test_base_abstrak(self):
        with self.assertRaises(TypeError):
            BaseAnalyzer()

    def test_polimorfisme(self):
        for cls in (TrendAnalyzer, KpiAnalyzer, ReviewerAnalyzer, EconometricAnalyzer, SegmentationAnalyzer):
            hasil = cls().run(self.df)
            self.assertIsInstance(hasil, dict)
            self.assertTrue(all(isinstance(v, pd.DataFrame) for v in hasil.values()))

    def test_kpi(self):
        kpi = KpiAnalyzer().run(self.df)["kpi_juru_ketik"]
        self.assertEqual(len(kpi), self.df["penulis"].nunique())
        self.assertTrue(kpi["rata_rating"].between(1, 5).all())

    def test_varians_korektor_dalam_0_1(self):
        r = ReviewerAnalyzer().run(self.df)["ringkasan_korektor"].set_index("metrik")["nilai"]
        self.assertTrue(0 <= r["varians_dijelaskan_korektor"] <= 1)
        self.assertGreater(r["varians_dijelaskan_juru_ketik"], 0.9)  # data sintetis: rating tetap per penulis

    def test_segmentasi_menemukan_kelompok(self):
        prof = SegmentationAnalyzer().run(self.df)["profil_klaster"]
        self.assertGreaterEqual(len(prof), 2)

    def test_segmentasi_data_sedikit(self):
        kecil = Preprocessor().transform(make_raw(n_writers=3, per_writer=12))
        with self.assertRaises(ModelError):
            SegmentationAnalyzer().run(kecil)

    def test_ols_cluster_cocok_dengan_sklearn(self):
        rng = np.random.default_rng(1)
        n = 600
        X = pd.DataFrame({"const": 1.0, "a": rng.normal(size=n), "b": rng.normal(size=n)})
        y = 2 + 0.5 * X["a"] - 0.3 * X["b"] + rng.normal(scale=0.5, size=n)
        res = ols_cluster(y.to_numpy(), X, np.repeat(np.arange(30), 20))
        lr = LinearRegression().fit(X[["a", "b"]], y)
        self.assertAlmostEqual(res.loc["a", "koef"], lr.coef_[0], places=6)
        self.assertAlmostEqual(res.loc["b", "koef"], lr.coef_[1], places=6)
        self.assertAlmostEqual(res.loc["const", "koef"], lr.intercept_, places=6)
        self.assertLess(res.loc["a", "p_value"], 0.001)

    def test_model_pengalaman_menangkap_efek_belajar(self):
        rng = np.random.default_rng(2)
        df = Preprocessor().transform(make_raw(n_writers=30, per_writer=40, seed=3))
        df["rating"] = (3 + 0.4 * df["log_exp"] + rng.normal(scale=0.2, size=len(df))).clip(1, 5)
        k = EconometricAnalyzer().run(df)["koefisien_model"]
        m1 = k[(k["model"] == "M1") & (k["variabel"] == "log_exp")]["koef"].iloc[0]
        self.assertGreater(m1, 0.2)


if __name__ == "__main__":
    unittest.main()
