from datetime import datetime, timezone
from db import connect
from ingest_ofsted import ingest as ingest_ofsted
from ingest_hmlr import ingest as ingest_hmlr
from discover_sources import discover_ons_release_metadata
from ingest_ons_rent import ingest as ingest_ons_rent

def now():
    return datetime.now(timezone.utc).isoformat()

def mark_failed(source_key, message):
    con = connect()
    con.execute("""
      UPDATE dataset_publication_state
      SET status='refresh_failed', last_checked_at=?
      WHERE source_key=?
    """, (now(), source_key))
    con.commit()
    con.close()
    print(source_key, "FAILED:", message)

def main():
    jobs = [
        ("ofsted_schools", ingest_ofsted),
        ("hmlr_ppd", ingest_hmlr),
        ("ons_pipr_hpi", ingest_ons_rent),
    ]
    for key, fn in jobs:
        try:
            print(key, fn())
        except Exception as e:
            # Last-known-good tables are kept because the ingesters publish transactionally.
            mark_failed(key, str(e))


if __name__ == "__main__":
    main()
