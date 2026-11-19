"""Membuat dashboard HTML satu file dari CSV penilaian.

Pemakaian:  python build_dashboard.py data/juru_ketiks.csv [output/dashboard_juru_ketik.html]
Hasilnya bisa dibuka langsung di browser (grafik memakai Chart.js dari CDN, perlu internet).
"""
import json
import os
import sys

import pandas as pd

from peopleanalytics.config import Settings
from peopleanalytics.pipeline import AnalyticsPipeline
from peopleanalytics.preprocessing import NEGATIF, POSITIF

R = lambda x, n=2: round(float(x), n)          # noqa: E731
NO = lambda label: int(str(label).split()[-1])  # "JK 12" -> 12  # noqa: E731


def kumpulkan(csv_path: str) -> dict:
    pipe = AnalyticsPipeline(Settings(db_path=":memory:"))
    pipe.run(csv_path, save_db=False)
    r, d = pipe.results, pipe.data

    grup = pd.cut(d.exp_n, [0, 10, 50, 200, 500, 10**6], labels=["1-10", "11-50", "51-200", "201-500", ">500"])
    g = d.groupby(grup, observed=True).agg(n=("rating", "size"), r=("rating", "mean"),
                                           p5=("rating_5", "mean"), s=("ada_kesalahan", "mean"))
    exp = [[k, int(v.n), R(v.r), R(v.p5 * 100, 1), R(v.s * 100, 2)] for k, v in g.iterrows()]
    pola = lambda kunci: [[int(h), int(v["size"]), R(v["mean"])]                      # noqa: E731
                          for h, v in d.groupby(kunci).rating.agg(["size", "mean"]).iterrows()]
    nama = {**{k: "+ " + k.replace("_", " ") for k in POSITIF}, **{k: "- " + k.replace("_", " ") for k in NEGATIF}}
    fl = sorted(([nama[k], int(d[k].sum()), R(d.loc[d[k] == 1, "rating"].mean())] for k in nama if d[k].sum() > 0),
                key=lambda x: -x[1])

    dist = pd.crosstab(d.korektor, d.rating, normalize="index") * 100
    kr = [[NO(x.korektor), int(x.n), R(x.rata_rating), R(x["std"]), R(x.pct_5 * 100, 1), R(x.pct_kesalahan * 100, 2),
           R(x.pct_ada_ulasan * 100, 1)] + [R(dist.loc[x.korektor].get(v, 0), 1) for v in (1, 2, 3, 4, 5)]
          for _, x in r["profil_korektor"].reset_index().iterrows()]
    klaster = r["klaster_per_juru_ketik"]["klaster"].to_dict()
    kpi = [[NO(x.penulis), int(x.n_penilaian), R(x.rata_rating), R(x.pct_5, 1), R(x.pct_kesalahan, 1), R(x.pct_rilis, 1),
            int(x.jml_korektor), R(x.tren_rating_per_tulisan, 3), klaster.get(x.penulis, -1)]
           for _, x in r["kpi_juru_ketik"].reset_index().iterrows()]
    return dict(
        s=pipe.summary(),
        T=[[x.bulan, int(x.n), R(x.rata_rating, 3), R(x.pct_5, 1), R(x.pct_salah, 2)]
           for _, x in r["tren_bulanan"].reset_index().iterrows() if x.n >= 20],
        exp=exp, hr=pola(d.created_at.dt.hour), dw=pola(d.created_at.dt.day_of_week), fl=fl, kr=kr, K=kpi,
        M=[[x.model, x.variabel, R(x.koef, 3), R(x.se_cluster, 3), R(x.p_value, 4), R(x.r2, 3)]
           for _, x in r["koefisien_model"].iterrows()],
        C=[[int(i), int(x.jumlah_penulis), R(x.rata_rating), R(x.pct_5, 1), R(x.pct_kesalahan, 1), R(x.pct_rilis, 1),
            R(x.median_volume, 0), int(x.peringkat_klaster)] for i, x in r["profil_klaster"].iterrows()],
        S=[[int(x.k), R(x.silhouette, 3)] for _, x in r["silhouette"].iterrows()],
        P=[[NO(x.penulis), int(x.n_penilaian), R(x.rata_rating), R(x.pct_kesalahan, 1), R(x.pct_rilis, 1),
            R(x.tren_rating_per_tulisan, 3)] for _, x in r["prioritas_pembinaan"].reset_index().iterrows()],
        rng=[str(d.created_at.min().date()), str(d.created_at.max().date())],
        rd=[R(d.rating.eq(i).mean() * 100, 1) for i in range(1, 6)],
    )


def main(csv_path: str, out_path: str) -> None:
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "template.html")
    html = open(tpl, encoding="utf-8").read().replace("__DATA__", json.dumps(kumpulkan(csv_path), separators=(",", ":")))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(html)
    print(f"Dashboard tersimpan: {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/juru_ketiks.csv",
         sys.argv[2] if len(sys.argv) > 2 else "output/dashboard_juru_ketik.html")
