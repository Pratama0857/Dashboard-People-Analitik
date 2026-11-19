"""Lapisan basis data SQLite (SCPMK-5): skema, koneksi, dan query SQL."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

import pandas as pd

from .exceptions import PeopleAnalyticsError

TABLE = "penilaian"
STORED_COLUMNS = [
    "penulis", "korektor", "created_at", "bulan", "rating", "rating_4plus", "rating_5",
    "skor_positif", "skor_negatif", "ada_kesalahan", "berita_rilis", "ada_ulasan", "exp_n",
]


class ReviewRepository:
    """Repository: menyembunyikan detail SQL dari lapisan analisis (enkapsulasi)."""

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._keep: sqlite3.Connection | None = None
        if db_path == ":memory:":  # koneksi tunggal agar data tidak hilang
            self._keep = sqlite3.connect(db_path)

    @contextmanager
    def _connect(self):
        if self._keep is not None:
            yield self._keep
            return
        folder = os.path.dirname(self._db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PeopleAnalyticsError(f"Galat basis data: {exc}") from exc
        finally:
            conn.close()

    def save(self, df: pd.DataFrame) -> int:
        out = df[STORED_COLUMNS].copy()
        out["created_at"] = out["created_at"].astype(str)
        with self._connect() as conn:
            out.to_sql(TABLE, conn, if_exists="replace", index=False)
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_penulis ON {TABLE}(penulis)")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_korektor ON {TABLE}(korektor)")
        return len(out)

    def _query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def kpi_per_writer(self, min_n: int = 1) -> pd.DataFrame:
        return self._query(
            f"""SELECT penulis,
                       COUNT(*) AS n_penilaian,
                       ROUND(AVG(rating), 3) AS rata_rating,
                       ROUND(100.0 * AVG(rating_5), 2) AS pct_5,
                       ROUND(100.0 * AVG(ada_kesalahan), 2) AS pct_kesalahan
                FROM {TABLE} GROUP BY penulis HAVING COUNT(*) >= ?
                ORDER BY rata_rating DESC""", (min_n,))

    def reviewer_profile(self) -> pd.DataFrame:
        return self._query(
            f"""SELECT korektor, COUNT(*) AS n, ROUND(AVG(rating), 3) AS rata_rating,
                       ROUND(100.0 * AVG(rating_5), 2) AS pct_5
                FROM {TABLE} GROUP BY korektor ORDER BY n DESC""")

    def monthly_trend(self) -> pd.DataFrame:
        return self._query(
            f"""SELECT bulan, COUNT(*) AS n, ROUND(AVG(rating), 3) AS rata_rating
                FROM {TABLE} GROUP BY bulan ORDER BY bulan""")
