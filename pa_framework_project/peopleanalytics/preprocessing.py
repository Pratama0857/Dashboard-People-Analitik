"""Pemuatan, validasi, pseudonimisasi, dan rekayasa fitur data penilaian.

Etika data HRM (SCPMK-5 People Analytics): ID asli diganti nomor urut (JK 1, JK 2, ...
Korektor 1, ...) berdasarkan jumlah penilaian, agar laporan dan dashboard tidak memuat ID asli.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .config import DEFAULT_SETTINGS, Settings
from .exceptions import DataValidationError

REQUIRED_COLUMNS = ["juru_ketik_id", "korektor_id", "rating", "ulasan", "created_at"]

POSITIF = {
    "berita_aktual": r"berita aktual",
    "angle_bagus": r"angle berita bagus",
    "data_lengkap": r"data lengkap",
    "eksklusif": r"eksklusif",
    "running_berita": r"running berita",
    "nyaman_dibaca": r"nyaman dibaca",
    "caption_lengkap": r"caption foto lengkap",
    "berita_lapangan": r"berita lapangan",
    "sumber_foto_orisinil": r"sumber foto orisinil",
    "narasumber_banyak": r"narasumber lebih dari satu",
}
NEGATIF = {
    "typo": r"typo",
    "aktif_pasif": r"aktif dan pasif",
    "kutipan_keliru": r"kutipan langsung",
    "salah_narasumber": r"kesalahan penulisan narasumber",
    "tanpa_5w1h": r"5w",
    "berita_rilis": r"\brilis\b|\brelease\b|berita rilis",
    "nilai_berita_kurang": r"nilai berita|news value",
    "alur_berbelit": r"alur berbelit",
    "tanpa_sumber_foto": r"tidak ada sumber foto",
    "tanpa_sumber_berita": r"tidak ada sumber berita",
    "plagiat": r"plagiat",
    "opini_wartawan": r"opini",
    "tidak_both_side": r"both side",
}


class Preprocessor:
    """Mengubah data mentah menjadi tabel siap analisis."""

    def __init__(self, settings: Settings = DEFAULT_SETTINGS):
        self.settings = settings

    # --- pemuatan & validasi -------------------------------------------------
    def load_csv(self, path: str | None = None) -> pd.DataFrame:
        path = path or self.settings.csv_path
        try:
            raw = pd.read_csv(path, sep=None, engine="python")   # koma atau titik koma
        except FileNotFoundError as exc:
            raise DataValidationError(f"File data tidak ditemukan: {path}") from exc
        except pd.errors.EmptyDataError as exc:
            raise DataValidationError(f"File data kosong: {path}") from exc
        self.validate(raw)
        return raw

    @staticmethod
    def validate(df: pd.DataFrame) -> None:
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise DataValidationError(f"Kolom wajib tidak ada: {missing}")
        if df.empty:
            raise DataValidationError("Data tidak memiliki baris.")

    # --- etika: pseudonimisasi ----------------------------------------------
    @staticmethod
    def _beri_nomor(ids: pd.Series, prefix: str) -> pd.Series:
        """Nomor urut 1..N; nomor 1 untuk ID dengan penilaian terbanyak (seri: urut ID)."""
        hitung = ids.value_counts().rename_axis("id").reset_index(name="n")
        hitung["kunci"] = hitung["id"].astype(str)
        hitung = hitung.sort_values(["n", "kunci"], ascending=[False, True]).reset_index(drop=True)
        peta = {v: f"{prefix} {i + 1}" for i, v in enumerate(hitung["id"])}
        return ids.map(peta)

    # --- transformasi utama --------------------------------------------------
    def transform(self, raw: pd.DataFrame) -> pd.DataFrame:
        self.validate(raw)
        df = raw.copy()
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        if df["rating"].median() > 5:                       # ekspor sistem memakai skala 10-50
            df["rating"] = df["rating"] / 10
        df = df[df["rating"].between(1, 5)].copy()
        if df.empty:
            raise DataValidationError("Tidak ada rating valid (1-5).")

        df["penulis"] = self._beri_nomor(df["juru_ketik_id"], "JK")
        df["korektor"] = self._beri_nomor(df["korektor_id"], "Korektor")
        tgl = pd.to_datetime(df["created_at"], format="%d/%m/%Y %H.%M", errors="coerce")
        if tgl.isna().any():                             # format lain (mis. ISO): coba parser umum
            tgl = tgl.fillna(pd.to_datetime(df["created_at"], errors="coerce", format="mixed"))
        df["created_at"] = tgl
        df = df.dropna(subset=["created_at"]).copy()
        df["ulasan"] = df["ulasan"].fillna("").replace("#NAME?", "")
        df["ada_ulasan"] = (df["ulasan"].str.strip() != "").astype(int)

        low = df["ulasan"].str.lower()
        for nama, pola in {**POSITIF, **NEGATIF}.items():
            df[nama] = low.str.contains(pola, regex=True).astype(int)
        df["skor_positif"] = df[list(POSITIF)].sum(axis=1)
        df["skor_negatif"] = df[list(NEGATIF)].sum(axis=1)
        df["ada_kesalahan"] = (df["skor_negatif"] > 0).astype(int)
        df["rating_4plus"] = (df["rating"] >= 4).astype(int)
        df["rating_5"] = (df["rating"] == 5).astype(int)

        df = df.sort_values(["penulis", "created_at"]).reset_index(drop=True)
        df["bulan"] = df["created_at"].dt.to_period("M").astype(str)
        df["t_bulan"] = (df["created_at"] - df["created_at"].min()).dt.days / 30.4
        df["exp_n"] = df.groupby("penulis").cumcount() + 1
        df["log_exp"] = np.log(df["exp_n"])
        return df

    def run(self, path: str | None = None) -> pd.DataFrame:
        return self.transform(self.load_csv(path))


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
