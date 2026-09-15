from datetime import datetime, timezone
from db import connect
from collectors import latest_police_month

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    con = connect()

    # Police.uk can expose its latest available month directly.
    try:
        month = latest_police_month()
        con.execute("""
          UPDATE dataset_publication_state
          SET status='source_checked', last_checked_at=?
          WHERE source_key='police_uk'
        """, (now(),))
        print("Police.uk latest available month:", month)
    except Exception as e:
        con.execute("""
          UPDATE dataset_publication_state
          SET status='refresh_check_failed', last_checked_at=?
          WHERE source_key='police_uk'
        """, (now(),))
        print("Police.uk freshness check failed:", e)

    # Bulk sources:
    # This job intentionally records/checks availability separately from publication.
    # Do not mark a new dataset as live until download + schema validation + row validation pass.
    for key in ("ofsted_schools", "hmlr_ppd", "ons_pipr_hpi", "ea_long_term_flood"):
        con.execute("""
          UPDATE dataset_publication_state
          SET last_checked_at=COALESCE(last_checked_at, ?)
          WHERE source_key=?
        """, (now(), key))

    con.commit()
    con.close()

if __name__ == "__main__":
    main()
