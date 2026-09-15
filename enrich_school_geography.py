from datetime import datetime, timezone
import requests
from db import connect

URL = "https://api.postcodes.io/postcodes"
UA = "NazufiUKLivingScore/0.3 (+https://www.nazufienterprise.com/)"

def now():
    return datetime.now(timezone.utc).isoformat()

def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def main():
    con = connect()
    rows = con.execute("""
      SELECT s.urn, s.postcode
      FROM schools s
      LEFT JOIN school_geography g ON g.urn=s.urn
      WHERE g.urn IS NULL AND s.postcode IS NOT NULL AND TRIM(s.postcode)<>''
      LIMIT 5000
    """).fetchall()

    pairs=[(r["urn"],r["postcode"]) for r in rows]
    by_pc={}
    for urn, pc in pairs:
        by_pc.setdefault(pc.strip().upper(), []).append(urn)

    postcodes=list(by_pc)
    updated=0
    for batch in chunks(postcodes, 100):
        resp=requests.post(URL, json={"postcodes":batch},
                           headers={"User-Agent":UA,"Accept":"application/json"}, timeout=60)
        resp.raise_for_status()
        data=resp.json()
        for item in data.get("result", []):
            query=(item.get("query") or "").strip().upper()
            result=item.get("result")
            if not result:
                continue
            lat=result.get("latitude"); lon=result.get("longitude")
            if lat is None or lon is None:
                continue
            for urn in by_pc.get(query, []):
                con.execute("""
                  INSERT INTO school_geography(urn, postcode, latitude, longitude, geocoded_at)
                  VALUES (?, ?, ?, ?, ?)
                  ON CONFLICT(urn) DO UPDATE SET
                    postcode=excluded.postcode, latitude=excluded.latitude,
                    longitude=excluded.longitude, geocoded_at=excluded.geocoded_at
                """, (urn, query, lat, lon, now()))
                updated += 1
        con.commit()
    con.close()
    print({"school_coordinates_updated":updated})

if __name__=="__main__":
    main()
