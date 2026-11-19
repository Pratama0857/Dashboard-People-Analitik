import os
import tempfile
import unittest

from peopleanalytics.config import Settings
from peopleanalytics.pipeline import AnalyticsPipeline
from tests.helpers import make_raw

REAL = "data/juru_ketiks.csv"


class PipelineTest(unittest.TestCase):
    def test_end_to_end_sintetis(self):
        with tempfile.TemporaryDirectory() as d:
            csv = os.path.join(d, "x.csv")
            make_raw(24, 30).to_csv(csv, index=False)
            pipe = AnalyticsPipeline(Settings(db_path=os.path.join(d, "t.db"), out_dir=os.path.join(d, "out")))
            pipe.run(csv)
            s = pipe.summary()
            self.assertEqual(s["jumlah_penilaian"], 24 * 30)
            files = pipe.export()
            self.assertTrue(all(os.path.exists(f) for f in files))
            self.assertTrue(os.path.exists(os.path.join(d, "t.db")))

    def test_summary_sebelum_run(self):
        with self.assertRaises(RuntimeError):
            AnalyticsPipeline().summary()

    @unittest.skipUnless(os.path.exists(REAL), "data asli tidak ada")
    def test_data_asli(self):
        pipe = AnalyticsPipeline(Settings(db_path=":memory:"))
        pipe.run(save_db=False)
        self.assertEqual(pipe.summary()["jumlah_penilaian"], 14742)


if __name__ == "__main__":
    unittest.main()
