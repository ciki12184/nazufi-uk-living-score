from datetime import datetime, timezone
import time
import requests

from db import connect

URL = "https://api.postcodes.io/postcodes"
UA = "NazufiUKLivingScore/0.4 (+https://www.nazufienterprise.com/)"


def now():
    return datetime.now(timezone.utc).isoformat()


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_pending(limit=5000):
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT s.urn, s.postcode
            FROM schools s
            LEFT JOIN school_geography g ON g.urn = s.urn
            WHERE g.urn IS NULL
              AND s.postcode IS NOT NULL
              AND TRIM(s.postcode) <> ''
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [(r["urn"], r["postcode"]) for r in rows]
    finally:
        con.close()


def geocode_pairs(pairs):
    by_pc = {}
    for urn, pc in pairs:
        key = pc.strip().upper()
        if key:
            by_pc.setdefault(key, []).append(urn)

    postcodes = list(by_pc)
    updated = 0

    con = connect()
    try:
        for batch in chunks(postcodes, 100):
            resp = requests.post(
                URL,
                json={"postcodes": batch},
                headers={"User-Agent": UA, "Accept": "application/json"},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("result", []):
                query = (item.get("query") or "").strip().upper()
                result = item.get("result")

                if not result:
                    continue

                lat = result.get("latitude")
                lon = result.get("longitude")

                if lat is None or lon is None:
                    continue

                for urn in by_pc.get(query, []):
                    con.execute(
                        """
                        INSERT INTO school_geography
                        (urn, postcode, latitude, longitude, geocoded_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(urn) DO UPDATE SET
                          postcode = excluded.postcode,
                          latitude = excluded.latitude,
                          longitude = excluded.longitude,
                          geocoded_at = excluded.geocoded_at
                        """,
                        (urn, query, lat, lon, now()),
                    )
                    updated += 1

            con.commit()
            time.sleep(0.05)

    finally:
        con.close()

    return updated


def main():
    total_updated = 0
    batches = 0

    while True:
        pending = fetch_pending(limit=5000)

        if not pending:
            break

        batches += 1
        updated = geocode_pairs(pending)
        total_updated += updated

        print({
            "batch": batches,
            "requested_school_rows": len(pending),
            "school_coordinates_updated": updated,
            "total_updated": total_updated,
        })

        # Prevent an endless loop if a whole batch contains postcodes that
        # cannot be geocoded by the official postcode service.
        if updated == 0:
            break

    print({
        "status": "complete",
        "batches": batches,
        "school_coordinates_updated": total_updated,
    })


if __name__ == "__main__":
    main()
