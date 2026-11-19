"""Pembuat data sintetis untuk pengujian."""
import numpy as np
import pandas as pd

TEMPLATE_BAIK = "- Data lengkap \\n- Berita Eksklusif \\n- Berita Aktual \\n- Angle Berita Bagus dan Unik \\n- Running Berita"
TEMPLATE_SEDANG = "- Tulisan nyaman dibaca \\n- Caption foto lengkap \\n- Berita lapangan"
TEMPLATE_BURUK = "- Terdapat typo \\n- Berita tidak mengandung 5w + 1h \\n- Berita release"


def make_raw(n_writers=20, per_writer=30, seed=0):
    rng = np.random.default_rng(seed)
    rows, rid = [], 1
    t0 = pd.Timestamp("2024-08-01")
    for w in range(1, n_writers + 1):
        base = rng.choice([0, 1, 2], p=[0.3, 0.4, 0.3])
        for i in range(per_writer):
            nilai = {0: (TEMPLATE_BURUK, 3), 1: (TEMPLATE_SEDANG, 4), 2: (TEMPLATE_BAIK, 5)}[base]
            rows.append({"id": rid, "post_id": 1000 + rid, "juru_ketik_id": w,
                         "korektor_id": int(rng.integers(1, 4)), "rating": nilai[1],
                         "ulasan": nilai[0], "created_at": t0 + pd.Timedelta(days=int(i * 5 + w))})
            rid += 1
    return pd.DataFrame(rows)
