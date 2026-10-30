"""QuickKart portfolio demo: generate simulated daily POS inputs from Neon.

Intended for a clean GitHub Actions workspace, NOT your existing local
QuickKart project, because it creates minimal CSV master fixtures in
01_Raw_Data/. It never modifies Neon or real historical transactions.

Usage:
  python scripts/generate_cloud_store_files.py
  python scripts/generate_cloud_store_files.py --date 2026-10-27

Requirements:
  pip install psycopg2-binary
  NEON_DATABASE_URL set as a GitHub Actions secret/environment variable.

The synthetic transactions are WEIGHTED by historical store/product/units
frequencies. They are NOT actual store POS submissions.
"""

import argparse
import csv
import os
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
STORE_FILES_EXPECTED = 50
ROWS_PER_STORE = 30


def get_report_date():
    parser = argparse.ArgumentParser(description="Generate simulated QuickKart POS CSV files from Neon")
    parser.add_argument("--date", help="Reporting date YYYY-MM-DD; default yesterday in IST")
    args = parser.parse_args()
    if args.date:
        return date.fromisoformat(args.date)
    return datetime.now(IST).date() - timedelta(days=1)


def read_cloud_reference_data(connection):
    """Return small reference sets; never download 829k transaction records."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT store_id FROM historical.stores ORDER BY store_id")
        store_ids = [int(r[0]) for r in cursor.fetchall()]
        cursor.execute("SELECT product_id FROM historical.products ORDER BY product_id")
        product_ids = [int(r[0]) for r in cursor.fetchall()]
        cursor.execute("""
            SELECT store_id, product_id, units, COUNT(*) AS frequency
            FROM historical.sales
            WHERE units > 0
            GROUP BY store_id, product_id, units
            ORDER BY store_id, product_id, units
        """)
        frequency_rows = cursor.fetchall()
    return store_ids, product_ids, frequency_rows


def validate_reference_data(store_ids, product_ids, frequency_rows):
    if len(store_ids) != STORE_FILES_EXPECTED or len(set(store_ids)) != STORE_FILES_EXPECTED:
        raise ValueError(f"Expected {STORE_FILES_EXPECTED} unique stores; got {len(store_ids)}")
    if not product_ids or len(set(product_ids)) != len(product_ids):
        raise ValueError("Product master is empty or contains duplicate product IDs")
    if any(x <= 0 for x in store_ids + product_ids):
        raise ValueError("Master store/product IDs must be positive")

    store_set, product_set = set(store_ids), set(product_ids)
    by_store = defaultdict(list)
    for sid, pid, units, frequency in frequency_rows:
        sid, pid, units, frequency = int(sid), int(pid), int(units), int(frequency)
        if sid not in store_set or pid not in product_set or units <= 0 or frequency <= 0:
            raise ValueError("Invalid historical store/product/unit frequency; refusing to generate")
        by_store[sid].append(((pid, units), frequency))
    missing = [sid for sid in store_ids if not by_store[sid]]
    if missing:
        raise ValueError(f"Stores have no usable sales history: {missing}")
    return by_store


def write_csv(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def generate_files(report_date, store_ids, product_ids, by_store, project_root=ROOT):
    """Write minimal QA master CSVs and simulated POS files in a clean workspace."""
    raw = project_root / "01_Raw_Data"
    daily = project_root / "02_Daily_Input" / report_date.isoformat()

    # Protect a user's pre-existing original local raw CSVs from replacement.
    if raw.is_dir() and any(raw.glob("*.csv")):
        raise FileExistsError(
            f"Refusing to overwrite existing source CSVs in {raw}. "
            "Use a clean GitHub Actions checkout, not the original local project."
        )
    if daily.exists() and any(daily.iterdir()):
        raise FileExistsError(f"Daily folder is not empty: {daily}; refusing to overwrite")

    raw.mkdir(parents=True, exist_ok=True)
    daily.mkdir(parents=True, exist_ok=True)
    # Minimal master fixtures for the ORIGINAL run_daily_quality_pipeline.py.
    write_csv(raw / "stores.csv", ["Store_ID"], ((s,) for s in store_ids))
    write_csv(raw / "products.csv", ["Product_ID"], ((p,) for p in product_ids))

    manifest = []
    serial = 1
    date_prefix = int(report_date.strftime("%Y%m%d")) * 100000
    for store_id in store_ids:
        pairs, weights = zip(*by_store[store_id])
        # Distinct reproducible selection for each date + store.
        rng = random.Random(f"{report_date.isoformat()}:{store_id}")
        simulated_transactions = rng.choices(pairs, weights=weights, k=ROWS_PER_STORE)
        filename = f"POS_{report_date.isoformat()}_S{store_id:03d}.csv"
        rows = []
        for product_id, units in simulated_transactions:
            rows.append((date_prefix + serial, report_date.isoformat(), store_id, product_id, units))
            serial += 1
        write_csv(daily / filename, ["Sale_ID", "Date", "Store_ID", "Product_ID", "Units"], rows)
        manifest.append((store_id, filename, "08:15", "SIMULATED"))

    write_csv(daily / "expected_files_manifest.csv",
              ["Store_ID", "Expected_File", "Expected_By", "Scenario"], manifest)
    return daily, serial - 1


def main():
    report_date = get_report_date()
    db_url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not db_url:
        raise SystemExit("ERROR: NEON_DATABASE_URL GitHub secret/environment variable is missing")

    # Neon requires SSL. Never print the URL or password.
    with psycopg2.connect(db_url, sslmode="require", connect_timeout=30) as conn:
        stores, products, frequencies = read_cloud_reference_data(conn)

    by_store = validate_reference_data(stores, products, frequencies)
    folder, row_count = generate_files(report_date, stores, products, by_store)
    print("PASS: SIMULATED POS FILES GENERATED FROM NEON HISTORICAL DISTRIBUTIONS")
    print(f"Report Date: {report_date}")
    print(f"Store Files: {len(stores)}")
    print(f"Simulated Transactions: {row_count}")
    print(f"Folder: {folder.relative_to(ROOT)}")
    print("This is a portfolio SIMULATION, not real POS data.")


if __name__ == "__main__":
    main()
