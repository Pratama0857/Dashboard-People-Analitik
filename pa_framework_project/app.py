"""Dashboard web (SCPMK-4: aplikasi web). Jalankan: streamlit run app.py"""
import pandas as pd
import streamlit as st

from peopleanalytics.config import Settings
from peopleanalytics.exceptions import PeopleAnalyticsError
from peopleanalytics.pipeline import AnalyticsPipeline

st.set_page_config(page_title="People Analytics Juru Ketik", layout="wide")
st.title("People Analytics: Kinerja Juru Ketik")
st.caption("ID juru ketik dan korektor sudah dipseudonimkan. Gunakan hasil untuk pengembangan, "
           "bukan satu-satunya dasar sanksi.")

upload = st.sidebar.file_uploader("Unggah juru_ketiks.csv", type="csv")
min_n = st.sidebar.slider("Minimal penilaian per juru ketik", 5, 100, 10)


@st.cache_data(show_spinner="Menjalankan analisis...")
def jalankan(file_bytes, min_n):
    import io
    settings = Settings(min_review_writer=min_n, db_path=":memory:")
    pipe = AnalyticsPipeline(settings)
    pipe.run(io.BytesIO(file_bytes), save_db=False)
    return pipe.results, pipe.summary(), pipe.warnings


if upload is None:
    st.info("Unggah file CSV di sidebar untuk memulai.")
    st.stop()

try:
    hasil, ringkas, warns = jalankan(upload.getvalue(), min_n)
except PeopleAnalyticsError as exc:
    st.error(f"Data tidak dapat diproses: {exc}")
    st.stop()

for w in warns:
    st.warning(w)

cols = st.columns(4)
cols[0].metric("Jumlah penilaian", f"{ringkas['jumlah_penilaian']:,}")
cols[1].metric("Rata-rata rating", ringkas["rata_rating"])
cols[2].metric("% rating 5", f"{ringkas['pct_rating_5']}%")
cols[3].metric("% ada kesalahan", f"{ringkas['pct_ada_kesalahan']}%")

t1, t2, t3, t4, t5 = st.tabs(["Tren", "KPI juru ketik", "Korektor", "Model", "Segmentasi"])
with t1:
    st.line_chart(hasil["tren_bulanan"]["rata_rating"])
    st.bar_chart(hasil["tren_bulanan"]["n"])
with t2:
    st.subheader("Prioritas pembinaan")
    st.dataframe(hasil["prioritas_pembinaan"])
    st.subheader("Seluruh juru ketik")
    st.dataframe(hasil["kpi_juru_ketik"])
with t3:
    st.dataframe(hasil["profil_korektor"])
    st.dataframe(hasil["ringkasan_korektor"])
with t4:
    if "koefisien_model" in hasil:
        st.dataframe(hasil["koefisien_model"])
with t5:
    if "profil_klaster" in hasil:
        st.dataframe(hasil["profil_klaster"])
        st.dataframe(hasil["silhouette"])
