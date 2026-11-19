import unittest

import pandas as pd

from peopleanalytics.exceptions import DataValidationError
from peopleanalytics.preprocessing import Preprocessor
from tests.helpers import make_raw


class PreprocessingTest(unittest.TestCase):
    def setUp(self):
        self.pre = Preprocessor()
        self.df = self.pre.transform(make_raw())

    def test_id_dipseudonimkan(self):
        self.assertTrue(self.df["penulis"].str.startswith("JK ").all())
        nomor = sorted(int(x.split()[1]) for x in set(self.df["penulis"]))
        self.assertEqual(nomor, list(range(1, len(nomor) + 1)))
        self.assertNotIn("1", set(self.df["penulis"]))

    def test_pseudonim_konsisten(self):
        a = self.pre.transform(make_raw())["penulis"].unique()
        b = self.pre.transform(make_raw())["penulis"].unique()
        self.assertEqual(set(a), set(b))

    def test_fitur_ulasan(self):
        self.assertTrue((self.df.loc[self.df["typo"] == 1, "ada_kesalahan"] == 1).all())
        self.assertTrue((self.df.loc[self.df["data_lengkap"] == 1, "skor_positif"] == 5).all())
        self.assertTrue((self.df.loc[self.df["berita_rilis"] == 1, "tanpa_5w1h"] == 1).all())

    def test_rating_di_luar_rentang_dibuang(self):
        raw = make_raw(3, 5)
        raw.loc[0, "rating"] = 9
        self.assertEqual(len(self.pre.transform(raw)), len(raw) - 1)

    def test_kolom_wajib_hilang(self):
        with self.assertRaises(DataValidationError):
            self.pre.transform(make_raw().drop(columns=["rating"]))

    def test_file_tidak_ada(self):
        with self.assertRaises(DataValidationError):
            self.pre.load_csv("tidak_ada.csv")

    def test_urutan_pengalaman(self):
        g = self.df[self.df["penulis"] == self.df["penulis"].iloc[0]]
        self.assertEqual(list(g["exp_n"]), list(range(1, len(g) + 1)))


if __name__ == "__main__":
    unittest.main()
