"""Kelas analisis (SCPMK-2: abstraksi, pewarisan, polimorfisme).

Semua analyzer mewarisi BaseAnalyzer dan memiliki antarmuka yang sama: run(df) -> dict tabel.
Pipeline cukup memanggil run() pada tiap objek tanpa peduli jenis analisisnya.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .config import DEFAULT_SETTINGS, Settings
from .exceptions import ModelError


class BaseAnalyzer(ABC):
    """Antarmuka (kelas abstrak) untuk semua analisis."""

    name = "base"

    def __init__(self, settings: Settings = DEFAULT_SETTINGS):
        self._settings = settings

    @abstractmethod
    def run(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Menjalankan analisis dan mengembalikan kumpulan tabel hasil."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class TrendAnalyzer(BaseAnalyzer):
    name = "tren"

    def run(self, df):
        tren = df.groupby("bulan").agg(n=("rating", "size"), rata_rating=("rating", "mean"),
                                       pct_5=("rating_5", "mean"), pct_salah=("ada_kesalahan", "mean"))
        tren[["pct_5", "pct_salah"]] *= 100
        dist = (df["rating"].value_counts(normalize=True).sort_index() * 100).rename("persen").to_frame()
        return {"tren_bulanan": tren.round(3), "distribusi_rating": dist.round(2)}


class KpiAnalyzer(BaseAnalyzer):
    """KPI per juru ketik + daftar prioritas pembinaan."""

    name = "kpi"

    @staticmethod
    def _slope(g: pd.DataFrame, min_n: int) -> float:
        if len(g) < min_n or g["exp_n"].nunique() < 3:
            return np.nan
        return float(np.polyfit(g["exp_n"], g["rating"], 1)[0])

    def run(self, df):
        min_n = self._settings.min_review_writer
        kpi = df.groupby("penulis").agg(
            n_penilaian=("rating", "size"), rata_rating=("rating", "mean"),
            pct_4plus=("rating_4plus", "mean"), pct_5=("rating_5", "mean"),
            pct_kesalahan=("ada_kesalahan", "mean"), pct_rilis=("berita_rilis", "mean"),
            jml_korektor=("korektor", "nunique"))
        kpi[["pct_4plus", "pct_5", "pct_kesalahan", "pct_rilis"]] *= 100
        kpi["tren_rating_per_tulisan"] = pd.Series(
            {k: self._slope(g, min_n) for k, g in df.groupby("penulis")})
        kpi = kpi.round(3).sort_values("n_penilaian", ascending=False)
        layak = kpi[kpi["n_penilaian"] >= min_n]
        prioritas = layak.sort_values(["rata_rating", "pct_kesalahan"],
                                      ascending=[True, False]).head(10)
        return {"kpi_juru_ketik": kpi, "prioritas_pembinaan": prioritas}


class ReviewerAnalyzer(BaseAnalyzer):
    """Profil korektor dan dekomposisi varians rating."""

    name = "korektor"

    @staticmethod
    def _between_share(df: pd.DataFrame, by: str) -> float:
        grand = df["rating"].mean()
        ss_total = ((df["rating"] - grand) ** 2).sum()
        if ss_total == 0:
            return 0.0
        g = df.groupby(by)["rating"].agg(["size", "mean"])
        return float((g["size"] * (g["mean"] - grand) ** 2).sum() / ss_total)

    def run(self, df):
        kor = df.groupby("korektor").agg(
            n=("rating", "size"), rata_rating=("rating", "mean"), std=("rating", "std"),
            pct_5=("rating_5", "mean"), pct_kesalahan=("ada_kesalahan", "mean"),
            pct_ada_ulasan=("ada_ulasan", "mean")).sort_values("n", ascending=False).round(3)
        besar = [g["rating"].values for _, g in df.groupby("korektor")
                 if len(g) >= self._settings.min_review_reviewer]
        h, p = (np.nan, np.nan)
        if len(besar) >= 2:
            h, p = stats.kruskal(*besar)
        ringkas = pd.DataFrame({
            "metrik": ["varians_dijelaskan_korektor", "varians_dijelaskan_juru_ketik",
                       "kruskal_H", "kruskal_p", "porsi_3_korektor_teraktif"],
            "nilai": [self._between_share(df, "korektor"), self._between_share(df, "penulis"),
                      h, p, kor["n"].head(3).sum() / kor["n"].sum()]}).round(4)
        return {"profil_korektor": kor, "ringkasan_korektor": ringkas}


def ols_cluster(y: np.ndarray, X: pd.DataFrame, groups: np.ndarray) -> pd.DataFrame:
    """OLS dengan galat standar robust ter-cluster (CR1, setara statsmodels cov_type='cluster').

    Implementasi manual agar koefisien dapat diaudit dan diuji tanpa bergantung pustaka tambahan.
    """
    A = X.to_numpy(dtype=float)
    n, k = A.shape
    XtX_inv = np.linalg.pinv(A.T @ A)
    beta = XtX_inv @ A.T @ y
    resid = y - A @ beta
    codes = pd.factorize(groups)[0]
    g = codes.max() + 1
    scores = pd.DataFrame(A * resid[:, None]).groupby(codes).sum().to_numpy()
    meat = scores.T @ scores
    c = (g / (g - 1)) * ((n - 1) / (n - k)) if g > 1 and n > k else 1.0
    V = c * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    z = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    p = 2 * (1 - stats.norm.cdf(np.abs(z)))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    out = pd.DataFrame({"koef": beta, "se_cluster": se, "z": z, "p_value": p}, index=X.columns)
    out.attrs["n"], out.attrs["r2"], out.attrs["clusters"] = n, float(r2), int(g)
    return out


class EconometricAnalyzer(BaseAnalyzer):
    """Model ekonometrika: pengaruh pengalaman dan waktu terhadap rating.

    M1: rating ~ log_exp + t_bulan
    M2: M1 + efek tetap korektor
    M3: M2 + efek tetap juru ketik (efek belajar within-writer)
    M4: rubrik (deskriptif; sirkular karena rating hampir deterministik terhadap poin ulasan)
    """

    name = "ekonometrika"

    @staticmethod
    def _design(df, base_cols, fe_cols=()):
        X = df[list(base_cols)].astype(float).copy()
        for fe in fe_cols:
            X = X.join(pd.get_dummies(df[fe], prefix=fe, drop_first=True, dtype=float))
        X.insert(0, "const", 1.0)
        return X

    def run(self, df):
        if df["penulis"].nunique() < 3 or len(df) < 30:
            raise ModelError("Data terlalu sedikit untuk model ekonometrika.")
        y = df["rating"].to_numpy(dtype=float)
        groups = df["penulis"].to_numpy()
        specs = {
            "M1": (["log_exp", "t_bulan"], []),
            "M2": (["log_exp", "t_bulan"], ["korektor"]),
            "M3": (["log_exp", "t_bulan"], ["korektor", "penulis"]),
            "M4_rubrik": (["skor_positif", "skor_negatif", "ada_ulasan"], []),
        }
        rows = []
        for nama, (cols, fes) in specs.items():
            res = ols_cluster(y, self._design(df, cols, fes), groups)
            for v in cols:
                r = res.loc[v]
                rows.append({"model": nama, "variabel": v, "koef": r["koef"],
                             "se_cluster": r["se_cluster"], "p_value": r["p_value"],
                             "n": res.attrs["n"], "r2": res.attrs["r2"],
                             "jumlah_cluster": res.attrs["clusters"]})
        return {"koefisien_model": pd.DataFrame(rows).round(4)}


class SegmentationAnalyzer(BaseAnalyzer):
    """Segmentasi juru ketik dengan KMeans (data mining)."""

    name = "segmentasi"
    FITUR = ["rata_rating", "pct_5", "pct_kesalahan", "pct_rilis"]

    def run(self, df):
        kpi = KpiAnalyzer(self._settings).run(df)["kpi_juru_ketik"]
        seg = kpi[kpi["n_penilaian"] >= self._settings.min_review_writer].copy()
        if len(seg) < 6:
            raise ModelError("Juru ketik layak segmentasi kurang dari 6.")
        seg["log_n"] = np.log(seg["n_penilaian"])
        X = StandardScaler().fit_transform(seg[self.FITUR + ["log_n"]])
        sil = {}
        for k in range(2, min(5, len(seg) - 1) + 1):
            lab = KMeans(n_clusters=k, n_init=20, random_state=self._settings.random_state).fit_predict(X)
            sil[k] = silhouette_score(X, lab)
        best_k = max(sil, key=sil.get)
        km = KMeans(n_clusters=best_k, n_init=20, random_state=self._settings.random_state).fit(X)
        seg["klaster"] = km.labels_
        profil = seg.groupby("klaster").agg(
            jumlah_penulis=("rata_rating", "size"), rata_rating=("rata_rating", "mean"),
            pct_5=("pct_5", "mean"), pct_kesalahan=("pct_kesalahan", "mean"),
            pct_rilis=("pct_rilis", "mean"), median_volume=("n_penilaian", "median")).round(2)
        profil["peringkat_klaster"] = profil["rata_rating"].rank(ascending=False, method="first").astype(int)
        silh = pd.DataFrame({"k": list(sil), "silhouette": list(sil.values())}).round(4)
        return {"profil_klaster": profil.sort_values("peringkat_klaster"),
                "klaster_per_juru_ketik": seg[["n_penilaian", "rata_rating", "pct_5",
                                               "pct_kesalahan", "pct_rilis", "klaster"]],
                "silhouette": silh}
