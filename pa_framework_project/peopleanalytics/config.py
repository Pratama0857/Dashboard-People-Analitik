"""Konfigurasi terpusat. Mengubah parameter cukup di satu tempat."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    csv_path: str = "data/juru_ketiks.csv"
    db_path: str = "data/penilaian.db"
    out_dir: str = "output"
    min_review_writer: int = 10      # minimal penilaian agar juru ketik masuk peringkat/segmen
    min_review_reviewer: int = 30    # minimal penilaian agar korektor dibandingkan
    random_state: int = 42


DEFAULT_SETTINGS = Settings()
