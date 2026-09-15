from db import connect

def save_postcode_area(r):
    con = connect()
    con.execute("""
      INSERT INTO postcode_areas
      (postcode, latitude, longitude, country, region, admin_district, lsoa, msoa, source_key, fetched_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'postcodes_io', ?)
      ON CONFLICT(postcode) DO UPDATE SET
        latitude=excluded.latitude,
        longitude=excluded.longitude,
        country=excluded.country,
        region=excluded.region,
        admin_district=excluded.admin_district,
        lsoa=excluded.lsoa,
        msoa=excluded.msoa,
        fetched_at=excluded.fetched_at
    """, (
        r["postcode"], r["latitude"], r["longitude"], r.get("country"), r.get("region"),
        r.get("admin_district"), r.get("lsoa"), r.get("msoa"), r["fetched_at"]
    ))
    con.commit()
    con.close()

def save_crime(postcode, s):
    con = connect()
    con.execute("""
      INSERT INTO crime_monthly(postcode, data_month, incident_count, fetched_at, source_key)
      VALUES (?, ?, ?, ?, 'police_uk')
      ON CONFLICT(postcode, data_month) DO UPDATE SET
        incident_count=excluded.incident_count,
        fetched_at=excluded.fetched_at
    """, (postcode, s["month"], s["incident_count"], s["fetched_at"]))
    con.execute(
        "DELETE FROM crime_category_monthly WHERE postcode=? AND data_month=?",
        (postcode, s["month"])
    )
    con.executemany("""
      INSERT INTO crime_category_monthly(postcode, data_month, category, incident_count)
      VALUES (?, ?, ?, ?)
    """, [(postcode, s["month"], k, v) for k, v in s["categories"].items()])
    con.commit()
    con.close()

def save_flood(postcode, s, status="ok"):
    con = connect()
    con.execute("""
      INSERT INTO flood_live_checks(postcode, checked_at, warning_count, source_key, status)
      VALUES (?, ?, ?, 'ea_flood_monitoring', ?)
    """, (postcode, s["checked_at"], s["warning_count"], status))
    con.commit()
    con.close()

def get_area(postcode):
    con = connect()
    row = con.execute("SELECT * FROM postcode_areas WHERE postcode=?", (postcode,)).fetchone()
    con.close()
    return dict(row) if row else None

def get_latest_crime(postcode):
    con = connect()
    month_row = con.execute("""
      SELECT * FROM crime_monthly WHERE postcode=?
      ORDER BY data_month DESC LIMIT 1
    """, (postcode,)).fetchone()
    if not month_row:
        con.close()
        return None
    cats = con.execute("""
      SELECT category, incident_count FROM crime_category_monthly
      WHERE postcode=? AND data_month=?
      ORDER BY incident_count DESC
    """, (postcode, month_row["data_month"])).fetchall()
    result = dict(month_row)
    result["categories"] = [dict(x) for x in cats]
    con.close()
    return result
