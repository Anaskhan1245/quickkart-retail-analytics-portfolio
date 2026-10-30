"""QuickKart Master Analytics | Simulated daily POS QA and approved CSV export.

Place this file in <QuickKart_Master_Analytics_Project>/scripts/.
Run from project root: python scripts\run_daily_quality_pipeline.py
Re-run historic date: python scripts\run_daily_quality_pipeline.py --date 2026-10-19

No third-party Python package is required. This script checks the *same*
simulated store files used by the Excel Power Query practice. It does not
refresh Excel or Power BI; that is a separate step.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "01_Raw_Data"
DAILY_INPUT = ROOT / "02_Daily_Input"
OUTPUT = ROOT / "03_Approved_Output"
LOGS = ROOT / "04_Automation_Logs"
SALES_COLS = ("Sale_ID", "Date", "Store_ID", "Product_ID", "Units")


def get_date():
    parser = argparse.ArgumentParser(description="Validate and export QuickKart simulated POS daily sales")
    parser.add_argument("--date", help="Report date YYYY-MM-DD; default: yesterday in IST")
    args = parser.parse_args()
    if args.date:
        try:
            return date.fromisoformat(args.date)
        except ValueError:
            parser.error("Use --date YYYY-MM-DD, for example --date 2026-10-19")
    return datetime.now(IST).date() - timedelta(days=1)


def find_master(kind):
    matches = [p for p in RAW.glob("*.csv")
               if p.stem.lower() == kind or p.stem.lower().endswith("_" + kind)]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {kind} CSV in {RAW}; found {len(matches)}")
    return matches[0]


def read_csv_file(path, required):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        actual_cols = reader.fieldnames or []
        missing_cols = [c for c in required if c not in actual_cols]
        if missing_cols:
            raise ValueError(f"{path.name}: missing column(s): {', '.join(missing_cols)}")
        return list(reader)


def valid_id(value):
    value = (value or "").strip()
    return int(value) if re.fullmatch(r"\d+", value) and int(value) > 0 else None


def main():
    report_date = get_date()
    day = report_date.isoformat()
    start = datetime.now(IST)
    input_folder = DAILY_INPUT / day
    approved_file = OUTPUT / f"Approved_Sales_{day}.csv"
    exception_file = LOGS / f"{day}_validation_exceptions.csv"
    status_file = LOGS / f"{day}_status.json"
    run_log = LOGS / f"{day}_{start.strftime('%H%M%S_%f')}_run.log"
    LOGS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    problems = []
    approved_rows = []
    expected_files = set()
    actual_files = set()
    seen_sale_ids = {}

    def issue(check, filename="", sale_id="", detail=""):
        problems.append({"Check": check, "Source_File": filename,
                         "Sale_ID": str(sale_id), "Reason": str(detail)})

    try:
        if not input_folder.is_dir():
            raise FileNotFoundError(f"Reporting folder not found: {input_folder}")

        # Master records determine known stores/products; no dummy IDs are allowed.
        stores = read_csv_file(find_master("stores"), ["Store_ID"])
        products = read_csv_file(find_master("products"), ["Product_ID"])
        store_ids = [valid_id(r["Store_ID"]) for r in stores]
        product_ids = [valid_id(r["Product_ID"]) for r in products]
        if None in store_ids or len(store_ids) != len(set(store_ids)):
            issue("INVALID_STORE_MASTER", detail="Blank/invalid/duplicate Store_ID")
        if None in product_ids or len(product_ids) != len(set(product_ids)):
            issue("INVALID_PRODUCT_MASTER", detail="Blank/invalid/duplicate Product_ID")
        known_stores = set(store_ids) - {None}
        known_products = set(product_ids) - {None}

        manifest_path = input_folder / "expected_files_manifest.csv"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Expected manifest not found: {manifest_path}")
        manifest = read_csv_file(manifest_path, ["Store_ID", "Expected_File"])
        manifest_ids, manifest_names = [], []
        for m in manifest:
            store_id = valid_id(m["Store_ID"])
            filename = (m["Expected_File"] or "").strip()
            manifest_ids.append(store_id)
            manifest_names.append(filename)
            if store_id not in known_stores:
                issue("UNKNOWN_STORE_IN_MANIFEST", filename, detail=f"Store_ID={m['Store_ID']}")
            if store_id is not None:
                expected_name = f"POS_{day}_S{store_id:03d}.csv"
                if filename != expected_name:
                    issue("MANIFEST_FILENAME_MISMATCH", filename,
                          detail=f"Expected {expected_name}")

        if len(manifest) != 50:
            issue("EXPECTED_FILE_COUNT_NOT_50", detail=f"Manifest rows={len(manifest)}")
        if Counter(manifest_names).most_common(1) and len(manifest_names) != len(set(manifest_names)):
            issue("DUPLICATE_EXPECTED_FILENAME")
        if len(manifest_ids) != len(set(manifest_ids)):
            issue("DUPLICATE_STORE_IN_MANIFEST")
        if set(manifest_ids) != known_stores:
            issue("MANIFEST_STORE_MASTER_MISMATCH",
                  detail=f"Missing stores={sorted(known_stores - set(manifest_ids))}; "
                         f"extra stores={sorted(set(manifest_ids) - known_stores, key=str)}")
        expected_files = set(manifest_names)
        actual_files = {p.name for p in input_folder.iterdir()
                        if p.is_file() and p.name.startswith("POS_") and p.suffix.lower() == ".csv"}
        for name in sorted(expected_files - actual_files):
            issue("MISSING_STORE_FILE", name)
        for name in sorted(actual_files - expected_files):
            issue("UNEXPECTED_STORE_FILE", name)

        # Read available expected files; leave raw input untouched.
        for filename in sorted(expected_files & actual_files):
            path = input_folder / filename
            try:
                rows = read_csv_file(path, SALES_COLS)
            except Exception as exc:
                issue("UNREADABLE_OR_WRONG_SCHEMA", filename, detail=exc)
                continue
            if not rows:
                issue("EMPTY_STORE_FILE", filename)
            store_match = re.fullmatch(rf"POS_{re.escape(day)}_S(\d+)\.csv", filename)
            filename_store_id = int(store_match.group(1)) if store_match else None
            for line, record in enumerate(rows, 2):
                sale_id = (record["Sale_ID"] or "").strip()
                store_id = valid_id(record["Store_ID"])
                product_id = valid_id(record["Product_ID"])
                units = valid_id(record["Units"])
                transaction_date = (record["Date"] or "").strip()
                notes = []
                if not sale_id or valid_id(sale_id) is None:
                    notes.append("Missing/invalid Sale_ID")
                if transaction_date != day:
                    notes.append(f"Wrong transaction Date ({transaction_date})")
                if store_id not in known_stores:
                    notes.append(f"Unknown/invalid Store_ID ({record['Store_ID']})")
                if product_id not in known_products:
                    notes.append(f"Unknown/invalid Product_ID ({record['Product_ID']})")
                if units is None:
                    notes.append(f"Units must be positive whole number ({record['Units']})")
                if filename_store_id is None or store_id != filename_store_id:
                    notes.append("Store_ID does not match source file name")
                if sale_id in seen_sale_ids:
                    notes.append(f"Duplicate Sale_ID (first found in {seen_sale_ids[sale_id]})")
                elif sale_id:
                    seen_sale_ids[sale_id] = filename
                if notes:
                    issue("INVALID_TRANSACTION", filename, sale_id,
                          f"CSV line {line}: " + "; ".join(notes))
                else:
                    approved_rows.append({
                        "Sale_ID": sale_id, "Date": day,
                        "Store_ID": str(store_id), "Product_ID": str(product_id),
                        "Units": str(units), "Source_File": filename
                    })

        if not approved_rows:
            issue("NO_VALID_TRANSACTIONS", detail="No transactions qualified for approved output")
    except Exception as exc:
        issue("PIPELINE_ERROR", detail=f"{type(exc).__name__}: {exc}")

    passed = not problems
    if passed:
        # Atomic replacement prevents half-written approved files.
        temporary = approved_file.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=[*SALES_COLS, "Source_File"])
                writer.writeheader()
                writer.writerows(approved_rows)
            os.replace(temporary, approved_file)
            if exception_file.exists():
                exception_file.unlink()  # Old exceptions not applicable to the now-passed run.
        except Exception as exc:
            passed = False
            issue("OUTPUT_WRITE_ERROR", detail=f"{type(exc).__name__}: {exc}")
            if temporary.exists():
                temporary.unlink()

    if not passed:
        # Never leave an approved file from an earlier run of this date looking current.
        if approved_file.exists():
            approved_file.unlink()
        with exception_file.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["Check", "Source_File", "Sale_ID", "Reason"])
            writer.writeheader()
            writer.writerows(problems)

    finished = datetime.now(IST)
    result = {
        "project": "QuickKart simulated daily reporting",
        "report_date": day,
        "status": "PASS" if passed else "BLOCKED",
        "expected_store_files": len(expected_files),
        "received_store_files": len(actual_files),
        "missing_files": len(expected_files - actual_files),
        "unexpected_files": len(actual_files - expected_files),
        "approved_transaction_rows": len(approved_rows) if passed else 0,
        "issue_count": len(problems),
        "run_at_ist": finished.isoformat(),
        "approved_csv": str(approved_file) if passed else None,
        "exception_csv": str(exception_file) if not passed else None,
    }
    status_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    log_lines = [f"QuickKart simulated daily run | {finished.isoformat()}",
                 f"Report Date: {day}", f"Status: {result['status']}",
                 f"Expected Files: {len(expected_files)} | Received POS Files: {len(actual_files)}",
                 f"Approved Rows: {result['approved_transaction_rows']}",
                 f"Issues: {len(problems)}"]
    for p in problems[:20]:
        log_lines.append(f"  - {p['Check']} | {p['Source_File']} | {p['Reason']}")
    log_lines.append(f"Execution seconds: {(finished - start).total_seconds():.2f}")
    run_log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n".join(log_lines))
    print("Status JSON:", status_file)
    print("Approved CSV:" if passed else "Exception CSV:", approved_file if passed else exception_file)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
