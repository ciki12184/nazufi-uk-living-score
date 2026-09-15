import csv, statistics
from collections import defaultdict
from datetime import datetime
from bulk_common import download_to_staging, sha256_file, utcnow
from discover_sources import discover_hmlr_current_month_csv
from db import connect

# HMLR PPD column order from the published Price Paid Data specification.
COLUMNS = [
    "transaction_id","price","transfer_date","postcode","property_type","old_new","duration",
    "paon","saon","street","locality","town_city","district","county","ppd_category","record_status"
]

ATTRIBUTION = "Contains HM Land Registry data © Crown copyright and database right 2021. This data is licensed under the Open Government Licence v3.0."

def clean(v):
    return (v or "").strip().strip('"')

def parse_row(row):
    if len(row) < 16:
        return None
    vals = dict(zip(COLUMNS, row[:16]))
    try:
        price = int(clean(vals["price"]))
        if price <= 0:
            return None
    except Exception:
        return None
    vals["price"] = price
    vals["transaction_id"] = clean(vals["transaction_id"]).strip("{}")
    vals["postcode"] = clean(vals["postcode"]).upper()
    vals["transfer_date"] = clean(vals["transfer_date"])[:10]
    return vals

def ingest():
    info = discover_hmlr_current_month_csv()
    path = download_to_staging(info["url"], "hmlr_current_month.csv")
    digest = sha256_file(path)
    fetched = utcnow()

    con = connect()
    existing = con.execute(
        "SELECT id FROM bulk_dataset_files WHERE source_key='hmlr_ppd' AND sha256=? AND is_published=1",
        (digest,)
    ).fetchone()
    if existing:
        con.close()
        return {"status":"unchanged","sha256":digest}

    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for raw in reader:
            r = parse_row(raw)
            if r:
                rows.append(r)

    if len(rows) < 100:
        con.close()
        raise RuntimeError(f"HMLR row-count validation failed: only {len(rows)} usable rows")

    # Current-month PPD is incomplete by design. Store evidence, but do not treat transaction
    # volume as a final market-volume measure.
    con.execute("BEGIN")
    try:
        for r in rows:
            con.execute("""
              INSERT INTO property_transactions
              (transaction_id, price, transfer_date, postcode, property_type, old_new, duration,
               paon, saon, street, locality, town_city, district, county, ppd_category,
               record_status, source_key, source_release, fetched_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'hmlr_ppd', ?, ?)
              ON CONFLICT(transaction_id) DO UPDATE SET
                price=excluded.price,
                transfer_date=excluded.transfer_date,
                postcode=excluded.postcode,
                property_type=excluded.property_type,
                old_new=excluded.old_new,
                duration=excluded.duration,
                paon=excluded.paon,
                saon=excluded.saon,
                street=excluded.street,
                locality=excluded.locality,
                town_city=excluded.town_city,
                district=excluded.district,
                county=excluded.county,
                ppd_category=excluded.ppd_category,
                record_status=excluded.record_status,
                source_release=excluded.source_release,
                fetched_at=excluded.fetched_at
            """, (
                r["transaction_id"],r["price"],r["transfer_date"],r["postcode"],r["property_type"],
                r["old_new"],r["duration"],r["paon"],r["saon"],r["street"],r["locality"],
                r["town_city"],r["district"],r["county"],r["ppd_category"],r["record_status"],
                info["label"],fetched
            ))

        con.execute("""
          INSERT INTO bulk_dataset_files
          (source_key, discovered_url, file_name, data_period, sha256, downloaded_at,
           validation_status, row_count, is_published)
          VALUES ('hmlr_ppd', ?, ?, ?, ?, ?, 'validated', ?, 1)
        """, (info["url"], path.name, info["label"], digest, fetched, len(rows)))

        con.execute("""
          UPDATE dataset_publication_state
          SET status='latest_available', last_checked_at=?
          WHERE source_key='hmlr_ppd'
        """, (fetched,))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    return {
        "status":"published",
        "rows":len(rows),
        "sha256":digest,
        "attribution":ATTRIBUTION,
        "warning":"Current-month PPD is incomplete and must not be used alone as final market-volume evidence."
    }

if __name__ == "__main__":
    print(ingest())
