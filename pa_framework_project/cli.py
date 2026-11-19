"""Aplikasi konsol (SCPMK-4: aplikasi berbasis konsol).

Contoh:
    python cli.py run --csv data/juru_ketiks.csv --out output
    python cli.py query kpi --min-n 20
    python cli.py query korektor
"""
import argparse
import logging
import sys

from peopleanalytics.config import Settings
from peopleanalytics.database import ReviewRepository
from peopleanalytics.exceptions import PeopleAnalyticsError
from peopleanalytics.pipeline import AnalyticsPipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="People Analytics - kinerja juru ketik")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="jalankan seluruh analisis")
    r.add_argument("--csv", default=Settings.csv_path)
    r.add_argument("--db", default=Settings.db_path)
    r.add_argument("--out", default=Settings.out_dir)
    q = sub.add_parser("query", help="query cepat ke basis data SQLite")
    q.add_argument("what", choices=["kpi", "korektor", "tren"])
    q.add_argument("--db", default=Settings.db_path)
    q.add_argument("--min-n", type=int, default=10)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if args.cmd == "run":
            pipe = AnalyticsPipeline(Settings(csv_path=args.csv, db_path=args.db, out_dir=args.out))
            pipe.run()
            for k, v in pipe.summary().items():
                print(f"{k:38s}: {v}")
            for f in pipe.export():
                print("tersimpan:", f)
            for w in pipe.warnings:
                print("PERINGATAN:", w)
        else:
            repo = ReviewRepository(args.db)
            table = {"kpi": lambda: repo.kpi_per_writer(args.min_n),
                     "korektor": repo.reviewer_profile, "tren": repo.monthly_trend}[args.what]()
            print(table.to_string(index=False))
        return 0
    except PeopleAnalyticsError as exc:
        print(f"GALAT: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
