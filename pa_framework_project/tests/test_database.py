import unittest

from peopleanalytics.database import ReviewRepository
from peopleanalytics.preprocessing import Preprocessor
from tests.helpers import make_raw


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.df = Preprocessor().transform(make_raw())
        self.repo = ReviewRepository(":memory:")
        self.n = self.repo.save(self.df)

    def test_jumlah_baris(self):
        self.assertEqual(self.n, len(self.df))

    def test_sql_sama_dengan_pandas(self):
        sql = self.repo.kpi_per_writer(1).set_index("penulis")["rata_rating"]
        pdv = self.df.groupby("penulis")["rating"].mean().round(3)
        for k in pdv.index:
            self.assertAlmostEqual(sql[k], pdv[k], places=3)

    def test_filter_min_n(self):
        self.assertEqual(len(self.repo.kpi_per_writer(10_000)), 0)

    def test_tren_dan_korektor(self):
        self.assertEqual(self.repo.reviewer_profile()["n"].sum(), len(self.df))
        self.assertEqual(self.repo.monthly_trend()["n"].sum(), len(self.df))


if __name__ == "__main__":
    unittest.main()
