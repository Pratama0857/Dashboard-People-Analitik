"""Dashboard Streamlit lengkap (6 tab + filter + detail per juru ketik).

Jalankan:  py -m streamlit run app_dashboard.py
Pakai data/juru_ketiks.csv otomatis, atau unggah CSV lewat sidebar. File lain di proyek tidak diubah.
"""
import inspect
import io
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from peopleanalytics.config import Settings
from peopleanalytics.exceptions import PeopleAnalyticsError
from peopleanalytics.pipeline import AnalyticsPipeline
from peopleanalytics.preprocessing import NEGATIF, POSITIF

st.set_page_config(page_title="Kinerja Juru Ketik", page_icon="📊", layout="wide")
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
PENG = ["1-10", "11-50", "51-200", "201-500", ">500"]
KW = {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters else {"use_container_width": True}
st.markdown("<style>.block-container{padding-top:1.5rem}div[data-testid=stMetric]{background:var(--secondary-background-color);"
            "padding:10px 14px;border-radius:12px}</style>", unsafe_allow_html=True)


def tampil(fig, tinggi=360):
    fig.update_layout(height=tinggi, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="")
    st.plotly_chart(fig, **KW)


def no(label):
    return int(str(label).split()[-1])


@st.cache_data(show_spinner="Menjalankan analisis...")
def muat(data: bytes):
    pipe = AnalyticsPipeline(Settings(db_path=":memory:"))
    pipe.run(io.BytesIO(data), save_db=False)
    r, d = pipe.results, pipe.data.copy()
    prof = r["profil_klaster"].reset_index()
    nama = {int(x.klaster): f"Klaster {int(x.peringkat_klaster)}" + (" (terbaik)" if x.peringkat_klaster == 1 else "")
            for _, x in prof.iterrows()}
    d["klaster"] = d.penulis.map(r["klaster_per_juru_ketik"]["klaster"].map(nama)).fillna("Belum diklaster")
    d["pengalaman"] = pd.cut(d.exp_n, [0, 10, 50, 200, 500, 10**6], labels=PENG).astype(str)
    d["tgl"], d["jam"] = d.created_at.dt.normalize(), d.created_at.dt.hour
    d["hari"] = d.created_at.dt.dayofweek.map(lambda i: HARI[i])
    d["rating_5"] = d.rating_5.astype(float)
    return d, r, nama, pipe.summary()


# ---------- sumber data & filter ----------
up = st.sidebar.file_uploader("Unggah juru_ketiks.csv", type="csv")
if up is not None:
    isi = up.getvalue()
elif os.path.exists("data/juru_ketiks.csv"):
    isi = open("data/juru_ketiks.csv", "rb").read()
else:
    st.info("Unggah file CSV di sidebar, atau taruh juru_ketiks.csv di folder data/.")
    st.stop()
try:
    D, R, NAMA, S = muat(isi)
except PeopleAnalyticsError as exc:
    st.error(f"Data tidak dapat diproses: {exc}")
    st.stop()

st.sidebar.header("Filter")
rg = st.sidebar.date_input("Rentang tanggal", (D.tgl.min().date(), D.tgl.max().date()))
kor = st.sidebar.multiselect("Korektor", sorted(D.korektor.unique(), key=no))
kla = st.sidebar.multiselect("Klaster", sorted(D.klaster.unique()))
pen = st.sidebar.multiselect("Pengalaman (jumlah tulisan)", PENG)
rat = st.sidebar.slider("Rentang rating", 1, 5, (1, 5))
F = D[D.rating.between(*rat)]
if isinstance(rg, tuple) and len(rg) == 2:
    F = F[(F.tgl >= pd.Timestamp(rg[0])) & (F.tgl <= pd.Timestamp(rg[1]))]
for kol, pil in (("korektor", kor), ("klaster", kla), ("pengalaman", pen)):
    if pil:
        F = F[F[kol].isin(pil)]
if F.empty:
    st.warning("Tidak ada data untuk filter ini.")
    st.stop()


def ringkas(g, by):
    return g.groupby(by).agg(n=("rating", "size"), rating=("rating", "mean"), p5=("rating_5", "mean"),
                             salah=("ada_kesalahan", "mean")).reset_index()


st.title("📊 People Analytics: Kinerja Juru Ketik")
st.caption(f"{len(F):,} dari {len(D):,} penilaian sesuai filter · {F.penulis.nunique()} juru ketik · {F.korektor.nunique()} korektor".replace(",", "."))
k = st.columns(6)
k[0].metric("Penilaian", f"{len(F):,}".replace(",", "."))
k[1].metric("Rata-rata rating", f"{F.rating.mean():.2f}", f"{F.rating.mean() - D.rating.mean():+.2f} vs semua")
k[2].metric("Rating ≥ 4", f"{(F.rating >= 4).mean():.1%}")
k[3].metric("Rating 5", f"{F.rating_5.mean():.1%}", f"{(F.rating_5.mean() - D.rating_5.mean()) * 100:+.1f} poin")
k[4].metric("Memuat kesalahan", f"{F.ada_kesalahan.mean():.1%}")
k[5].metric("Beri ulasan", f"{F.ada_ulasan.mean():.1%}")

t = st.tabs(["Ringkasan", "Tren & Pola", "Juru Ketik", "Korektor", "Kualitas & Model", "Segmentasi", "Data"])

# ---------- 1. Ringkasan ----------
with t[0]:
    bln = ringkas(F, "bulan").assign(bulan=lambda x: x.bulan.astype(str)).sort_values("bulan")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=bln.bulan, y=bln.n, name="Jumlah penilaian", opacity=.45)
    fig.add_scatter(x=bln.bulan, y=bln.rating, name="Rata-rata rating", mode="lines+markers", secondary_y=True)
    fig.update_yaxes(range=[1, 5], secondary_y=True, title="Rating")
    fig.update_layout(title="Tren bulanan")
    a, b = st.columns([3, 2])
    with a:
        tampil(fig)
    with b:
        dist = F.rating.value_counts(normalize=True).sort_index().mul(100).reset_index()
        dist.columns = ["rating", "persen"]
        tampil(px.bar(dist, x="rating", y="persen", title="Distribusi rating (%)", text_auto=".1f"))
    pj = ringkas(F[F.exp_n.notna()], "pengalaman").set_index("pengalaman").reindex(PENG).dropna()
    if len(pj) > 1:
        st.info(f"**Temuan:** rating rata-rata naik dari {pj.rating.iloc[0]:.2f} (pengalaman {pj.index[0]} tulisan) ke "
                f"{pj.rating.iloc[-1]:.2f} (pengalaman {pj.index[-1]}); penilaian bermuatan kesalahan turun dari "
                f"{pj.salah.iloc[0]:.1%} ke {pj.salah.iloc[-1]:.1%}. Korektor menjelaskan "
                f"{S['varians_dijelaskan_korektor_pct']:.1f}% variasi rating, juru ketik {S['varians_dijelaskan_juru_ketik_pct']:.1f}%.")

# ---------- 2. Tren & Pola ----------
with t[1]:
    a, b = st.columns(2)
    with a:
        fig = go.Figure()
        fig.add_scatter(x=bln.bulan, y=bln.p5 * 100, name="% rating 5", mode="lines+markers")
        fig.add_scatter(x=bln.bulan, y=bln.salah * 100, name="% memuat kesalahan", mode="lines+markers")
        fig.update_layout(title="Kualitas bulanan (%)")
        tampil(fig)
    with b:
        hr = F.groupby("tgl").rating.mean().rolling(30, min_periods=7).mean().reset_index()
        tampil(px.line(hr, x="tgl", y="rating", title="Rata-rata bergerak 30 hari"))
    a, b = st.columns(2)
    with a:
        pg = ringkas(F, "pengalaman").set_index("pengalaman").reindex(PENG).dropna().reset_index()
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=pg.pengalaman, y=pg.rating, name="Rata-rata rating")
        fig.add_scatter(x=pg.pengalaman, y=pg.p5 * 100, name="% rating 5", secondary_y=True)
        fig.update_yaxes(range=[3.5, 5], secondary_y=False)
        fig.update_layout(title="Rating menurut pengalaman")
        tampil(fig)
    with b:
        ukur = st.radio("Heatmap hari × jam", ["Jumlah penilaian", "Rata-rata rating"], horizontal=True)
        pv = F.pivot_table(index="hari", columns="jam", values="rating", aggfunc="size" if ukur[0] == "J" else "mean").reindex(HARI)
        tampil(px.imshow(pv, aspect="auto", color_continuous_scale="Blues", title=ukur))

# ---------- 3. Juru Ketik ----------
JK = ringkas(F, "penulis").merge(F.groupby("penulis").agg(korektor=("korektor", "nunique"), klaster=("klaster", "first")).reset_index())
JK["no_jk"] = JK.penulis.map(no)
with t[2]:
    mn = st.slider("Minimal penilaian per juru ketik", 1, 200, 10)
    J = JK[JK.n >= mn].sort_values("no_jk")
    a, b = st.columns(2)
    with a:
        tampil(px.scatter(J, x="n", y="rating", color="klaster", hover_name="penulis", log_x=True, title="Volume vs rating"))
    with b:
        tampil(px.histogram(J, x="rating", nbins=20, title="Sebaran rata-rata rating juru ketik"))
    st.dataframe(J.assign(p5=J.p5 * 100, salah=J.salah * 100)[["penulis", "n", "rating", "p5", "salah", "korektor", "klaster"]]
                 .rename(columns={"n": "Penilaian", "rating": "Rating", "p5": "% rating 5", "salah": "% salah", "korektor": "Jml korektor"}),
                 hide_index=True, column_config={"Rating": st.column_config.ProgressColumn(min_value=1, max_value=5, format="%.2f"),
                                                 "% rating 5": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                                                 "% salah": st.column_config.NumberColumn(format="%.1f")})
    st.subheader("Prioritas pembinaan")
    st.dataframe(R["prioritas_pembinaan"].reset_index())
    st.subheader("Detail satu juru ketik")
    pilih = st.selectbox("Pilih juru ketik", sorted(F.penulis.unique(), key=no))
    g = F[F.penulis == pilih].sort_values("created_at").reset_index(drop=True)
    c = st.columns(4)
    c[0].metric("Penilaian", len(g))
    c[1].metric("Rata-rata rating", f"{g.rating.mean():.2f}", f"{g.rating.mean() - D.rating.mean():+.2f} vs semua")
    c[2].metric("% rating 5", f"{g.rating_5.mean():.0%}")
    c[3].metric("% memuat kesalahan", f"{g.ada_kesalahan.mean():.1%}")
    a, b = st.columns([3, 2])
    with a:
        g["urutan"], g["rata_bergerak"] = g.index + 1, g.rating.rolling(5, min_periods=1).mean()
        fig = px.scatter(g, x="urutan", y="rating", title="Perkembangan rating per tulisan")
        fig.add_scatter(x=g.urutan, y=g.rata_bergerak, mode="lines", name="Rata-rata 5 tulisan")
        fig.add_hline(y=D.rating.mean(), line_dash="dot", annotation_text="rata-rata semua")
        tampil(fig, 320)
    with b:
        kg = ringkas(g, "korektor").assign(korektor=lambda x: x.korektor.astype(str))
        tampil(px.bar(kg, x="korektor", y="rating", text="n", title="Rating menurut korektor (angka = jumlah)"), 320)

# ---------- 4. Korektor ----------
with t[3]:
    F2 = F.assign(sisa=F.rating - F.groupby("penulis").rating.transform("mean"))
    KR = ringkas(F2, "korektor").merge(F2.groupby("korektor").agg(std=("rating", "std"), sisa=("sisa", "mean"),
                                                                  ulasan=("ada_ulasan", "mean")).reset_index())
    KR["no"] = KR.korektor.map(no)
    KR = KR.sort_values("no")
    KR["andal"] = KR.n >= Settings().min_review_reviewer
    KR["status"] = KR.andal.map({True: f"Cukup data (≥{Settings().min_review_reviewer} penilaian)", False: "Data sedikit"})
    KR["kor"] = KR.korektor.map(no)
    a, b = st.columns(2)
    with a:
        tampil(px.bar(KR, x="kor", y="rating", color="status", text="n", title="Rata-rata rating (angka = jumlah penilaian)")
               .update_xaxes(type="category", title="Korektor").update_yaxes(range=[1, 5]))
    with b:
        sisa = KR[KR.andal]
        tampil(px.bar(sisa, x="kor", y="sisa", title="Kemurahan hati: selisih rating terhadap rata-rata juru ketik yang sama")
               .update_xaxes(type="category", title="Korektor"))
    a, b = st.columns(2)
    with a:
        ct = pd.crosstab(F.korektor, F.rating, normalize="index").mul(100).reindex(KR.korektor)
        ct.index, ct.columns = KR.kor.values, [f"Rating {int(c)}" for c in ct.columns]
        tampil(px.bar(ct, barmode="stack", title="Komposisi rating per korektor (%)").update_xaxes(type="category", title="Korektor"))
    with b:
        hm = F.pivot_table(index="korektor", columns=F.bulan.astype(str), values="rating", aggfunc="mean").reindex(KR[KR.andal].korektor)
        tampil(px.imshow(hm, aspect="auto", color_continuous_scale="RdYlGn", zmin=3.5, zmax=5, title="Rating korektor × bulan"))
    st.dataframe(KR.drop(columns=["no", "kor", "status"]).rename(columns={"n": "Penilaian", "rating": "Rating", "p5": "% rating 5", "salah": "% salah"}), hide_index=True)

# ---------- 5. Kualitas & Model ----------
with t[4]:
    baris = []
    for kol in list(POSITIF) + list(NEGATIF):
        if F[kol].sum() > 0 and (F[kol] == 0).any():
            baris.append({"poin": kol.replace("_", " "), "jenis": "positif" if kol in POSITIF else "negatif", "jumlah": int(F[kol].sum()),
                          "dampak": F.loc[F[kol] == 1, "rating"].mean() - F.loc[F[kol] == 0, "rating"].mean()})
    P = pd.DataFrame(baris).sort_values("jumlah", ascending=False)
    a, b = st.columns(2)
    cm = {"positif": "#10b981", "negatif": "#dc2626"}
    with a:
        tampil(px.bar(P, y="poin", x="jumlah", color="jenis", orientation="h", color_discrete_map=cm, title="Poin ulasan paling sering").update_yaxes(autorange="reversed"), 460)
    with b:
        tampil(px.bar(P.sort_values("dampak"), y="poin", x="dampak", color="jenis", orientation="h", color_discrete_map=cm,
                      title="Selisih rating saat poin muncul vs tidak muncul"), 460)
    st.subheader("Model regresi (seluruh data, SE ter-cluster per juru ketik)")
    M = R["koefisien_model"].copy()
    M["lo"], M["hi"] = M.koef - 1.96 * M.se_cluster, M.koef + 1.96 * M.se_cluster
    fig = px.scatter(M, x="koef", y="variabel", color="model", error_x=M.hi - M.koef, error_x_minus=M.koef - M.lo,
                     title="Koefisien dengan interval kepercayaan 95%")
    fig.add_vline(x=0, line_dash="dot")
    tampil(fig)
    st.dataframe(M, hide_index=True)

# ---------- 6. Segmentasi ----------
with t[5]:
    PK = R["profil_klaster"].reset_index()
    PK["klaster"] = PK.klaster.map(NAMA)
    a, b = st.columns(2)
    with a:
        st.dataframe(PK, hide_index=True)
        sil = R["silhouette"]
        tampil(px.bar(sil, x="k", y="silhouette", title="Silhouette per jumlah klaster"), 260)
    with b:
        ukuran = ["rata_rating", "pct_5", "pct_rilis", "median_volume", "pct_kesalahan"]
        fig = go.Figure()
        for _, x in PK.iterrows():
            nilai = [x[u] / PK[u].replace(0, float("nan")).max() if PK[u].max() > 0 else 0 for u in ukuran]
            fig.add_scatterpolar(r=nilai + nilai[:1], theta=ukuran + ukuran[:1], fill="toself", name=x.klaster)
        fig.update_layout(title="Profil klaster (relatif terhadap nilai tertinggi)")
        tampil(fig, 420)
    pk = st.selectbox("Anggota klaster", sorted(D.klaster.unique()))
    st.dataframe(JK.merge(D[D.klaster == pk][["penulis"]].drop_duplicates())[["penulis", "n", "rating", "p5", "salah"]], hide_index=True)

# ---------- 7. Data ----------
with t[6]:
    tampil_kol = ["tgl", "bulan", "jam", "hari", "penulis", "korektor", "rating", "ada_kesalahan", "ada_ulasan", "skor_positif",
                  "skor_negatif", "pengalaman", "exp_n", "klaster"]
    st.dataframe(F[tampil_kol].sort_values("tgl"), hide_index=True)
    st.download_button("Unduh data terfilter (CSV)", F[tampil_kol].to_csv(index=False).encode("utf-8"), "penilaian_terfilter.csv", "text/csv")