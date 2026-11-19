# People Analytics Juru Ketik

Proyek gabungan **People Analytics (SD221207)** dan **Framework Pengembangan Perangkat Lunak (SD221242)**.
Aplikasi menganalisis penilaian korektor terhadap juru ketik berita (14.742 penilaian, 190 juru ketik,
16 korektor) dan menyajikannya lewat aplikasi konsol dan dashboard web.

## Menjalankan
```bash
pip install -r requirements.txt
cp /lokasi/juru_ketiks.csv data/          # CSV tidak ikut di repositori (data personal)
python cli.py run                          # analisis lengkap -> output/*.csv + data/penilaian.db
python cli.py query kpi --min-n 50         # query SQL cepat
streamlit run app.py                       # dashboard web Streamlit (unggah CSV di sidebar)
python build_dashboard.py data/juru_ketiks.csv   # dashboard HTML satu file -> output/dashboard_juru_ketik.html
python -m unittest discover -s tests -t . -v   # 22 pengujian
```

## Struktur
| Berkas | Peran |
|---|---|
| `peopleanalytics/preprocessing.py` | validasi, penomoran ID (anonim), fitur dari teks ulasan |
| `peopleanalytics/database.py` | repository SQLite, query SQL (`GROUP BY`, `HAVING`, parameter `?`) |
| `peopleanalytics/analyzers.py` | `BaseAnalyzer` (abstrak) + 5 analyzer turunan, OLS ter-cluster |
| `peopleanalytics/pipeline.py` | orkestrasi muat -> DB -> analisis -> ekspor |
| `cli.py` / `app.py` | aplikasi konsol / aplikasi web (Streamlit) |
| `build_dashboard.py` + `dashboard/template.html` | dashboard HTML interaktif 6 tab (tren, juru ketik, korektor, kualitas & model, segmentasi) |
| `tests/` | unit & integration test (`unittest`, juga terbaca `pytest`) |

## Pemetaan ke RPS Framework Pengembangan Perangkat Lunak
| Sub-CPMK | Wujud di proyek |
|---|---|
| SCPMK1 pemrograman dasar | struktur keputusan/pengulangan di analyzer; hierarki exception (`exceptions.py`), `try/except/finally` di `database.py` dan `pipeline.py` |
| SCPMK2 OOP | kelas, enkapsulasi (`_beri_nomor`, `_connect`), pewarisan dan polimorfisme (`BaseAnalyzer`), kelas abstrak (`ABC`) |
| SCPMK3 siklus hidup & pengujian | model Agile di bawah; unit test, integration test, pengujian terhadap data asli |
| SCPMK4 aplikasi web & desktop | `app.py` (web), `cli.py` (konsol) |
| SCPMK5 basis data | SQLite, skema, indeks, query SQL |
| SCPMK6 proyek PjBL | seluruh proyek + laporan + presentasi |

## Pemetaan ke RPS People Analytics
| Sub-CPMK | Wujud di proyek |
|---|---|
| SCPMK2 pengumpulan & analisis data HRM | `preprocessing.py`, `TrendAnalyzer`, `KpiAnalyzer` |
| SCPMK3 merancang & mengevaluasi program | KPI per juru ketik, daftar prioritas pembinaan |
| SCPMK4 komunikasi hasil | dashboard `app.py`, tabel ekspor |
| SCPMK5 etika data HRM | penomoran ID (anonim), peringatan di dashboard, catatan penggunaan |
| SCPMK6 proyek (model ekonometrika) | `EconometricAnalyzer` (M1-M4), `SegmentationAnalyzer` |

## Siklus pengembangan (Agile, 1 sprint = 1 minggu, selaras minggu 9-15 RPS)
| Sprint | Fokus | Keluaran |
|---|---|---|
| 1 (mg 9) | kebutuhan & topik | backlog, Bab 1 |
| 2 (mg 10) | data & basis data | `preprocessing`, `database` + test |
| 3 (mg 11) | analisis | analyzer, model |
| 4 (mg 12) | antarmuka | `cli.py`, `app.py` |
| 5 (mg 13) | pengujian | cakupan test, perbaikan bug |
| 6 (mg 14) | laporan | Bab 2-3 |
| 7 (mg 15) | finalisasi | Bab 4, lampiran, presentasi |

## Catatan data
- CSV memakai pemisah titik koma, rating berskala 10-50 (dibagi 10), tanggal `dd/mm/yyyy jj.mm`; kolom ulasan berisi `#NAME?` (sisa error Excel) dianggap kosong. Semua ditangani `preprocessing.py`.
- Juru ketik dan korektor diberi nomor urut (JK 1-190, Korektor 1-16) menurut jumlah penilaian terbanyak; ID asli tidak dipakai di keluaran.

## Catatan metodologi
- Rating hampir deterministik terhadap poin checklist ulasan, jadi model M4 (rubrik) hanya deskriptif.
  Pertanyaan utama dijawab lewat M1-M3 (pengalaman, tren waktu, efek tetap korektor dan juru ketik).
- OLS ter-cluster ditulis sendiri (`ols_cluster`) dan diuji terhadap scikit-learn, jadi tidak perlu `statsmodels`.
- Kolom aspek (typo, foto, caption, dst.) hanya terisi 0,2-3,9%, sehingga tidak dipakai sebagai variabel.
- Penugasan korektor ke penulis mungkin tidak acak; pengaruh korektor dibaca sebagai indikasi.
- Gunakan hasil untuk pengembangan juru ketik, bukan satu-satunya dasar sanksi.
