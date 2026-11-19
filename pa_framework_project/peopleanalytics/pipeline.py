"""Orkestrasi alur kerja: muat -> bersihkan -> simpan DB -> analisis -> ekspor."""
from __future__ import annotations

import logging
import os

import pandas as pd

from .analyzers import (BaseAnalyzer, EconometricAnalyzer, KpiAnalyzer, ReviewerAnalyzer,
                        SegmentationAnalyzer, TrendAnalyzer)
from .config import DEFAULT_SETTINGS, Settings
from .database import ReviewRepository
from .exceptions import ModelError
from .preprocessing import Preprocessor, ensure_dir

log = logging.getLogger("peopleanalytics")


class AnalyticsPipeline:
    def __init__(self, settings: Settings = DEFAULT_SETTINGS, analyzers: list[BaseAnalyzer] | None = None):
        self.settings = settings
        self.preprocessor = Preprocessor(settings)
        self.analyzers = analyzers or [TrendAnalyzer(settings), KpiAnalyzer(settings),
                                       ReviewerAnalyzer(settings), EconometricAnalyzer(settings),
                                       SegmentationAnalyzer(settings)]
        self.data: pd.DataFrame | None = None
        self.results: dict[str, pd.DataFrame] = {}
        self.warnings: list[str] = []

    def run(self, csv_path: str | None = None, save_db: bool = True) -> dict[str, pd.DataFrame]:
        self.data = self.preprocessor.run(csv_path)
        if save_db:
            n = ReviewRepository(self.settings.db_path).save(self.data)
            log.info("%d baris disimpan ke %s", n, self.settings.db_path)
        self.results, self.warnings = {}, []
        for analyzer in self.analyzers:           # polimorfisme: antarmuka run() sama
            try:
                self.results.update(analyzer.run(self.data))
            except ModelError as exc:              # satu analisis gagal tidak menghentikan yang lain
                msg = f"{analyzer.name}: {exc}"
                self.warnings.append(msg)
                log.warning(msg)
        return self.results

    def summary(self) -> dict:
        if self.data is None:
            raise RuntimeError("Jalankan run() terlebih dahulu.")
        d = self.data
        out = {
            "jumlah_penilaian": int(len(d)),
            "jumlah_juru_ketik": int(d["penulis"].nunique()),
            "jumlah_korektor": int(d["korektor"].nunique()),
            "rata_rating": round(float(d["rating"].mean()), 3),
            "pct_rating_4plus": round(float(d["rating_4plus"].mean() * 100), 1),
            "pct_rating_5": round(float(d["rating_5"].mean() * 100), 1),
            "pct_ada_kesalahan": round(float(d["ada_kesalahan"].mean() * 100), 1),
        }
        ring = self.results.get("ringkasan_korektor")
        if ring is not None:
            m = dict(zip(ring["metrik"], ring["nilai"]))
            out["varians_dijelaskan_korektor_pct"] = round(m["varians_dijelaskan_korektor"] * 100, 1)
            out["varians_dijelaskan_juru_ketik_pct"] = round(m["varians_dijelaskan_juru_ketik"] * 100, 1)
        return out

    def export(self, out_dir: str | None = None) -> list[str]:
        out_dir = ensure_dir(out_dir or self.settings.out_dir)
        files = []
        for name, table in self.results.items():
            path = os.path.join(out_dir, f"{name}.csv")
            table.to_csv(path)
            files.append(path)
        return files
