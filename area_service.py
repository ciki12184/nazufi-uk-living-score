from math import radians, sin, cos, asin, sqrt
from db import connect

def haversine_km(lat1, lon1, lat2, lon2):
    R=6371.0088
    dlat=radians(lat2-lat1)
    dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*R*asin(sqrt(a))

def nearby_schools(lat, lon, max_km=3.0, limit=12):
    con=connect()
    # Coarse bounding box first for performance.
    dlat=max_km/111.0
    dlon=max_km/(111.0*max(0.2, cos(radians(lat))))
    rows=con.execute("""
      SELECT s.urn,s.school_name,s.postcode,s.local_authority,s.phase,
             s.latest_inspection_date,s.latest_inspection_type,
             s.overall_effectiveness,s.safeguarding,s.data_period,s.fetched_at,
             g.latitude,g.longitude
      FROM schools s JOIN school_geography g ON g.urn=s.urn
      WHERE g.latitude BETWEEN ? AND ?
        AND g.longitude BETWEEN ? AND ?
    """,(lat-dlat,lat+dlat,lon-dlon,lon+dlon)).fetchall()
    con.close()
    out=[]
    for r in rows:
        d=haversine_km(lat,lon,r["latitude"],r["longitude"])
        if d<=max_km:
            x=dict(r); x["distance_km"]=round(d,2); out.append(x)
    return sorted(out,key=lambda x:x["distance_km"])[:limit]

def property_sales_prefix(postcode, limit=25):
    pc=postcode.replace(" ","").upper()
    # Full postcode first; then outward-code evidence if exact is sparse.
    outward=postcode.strip().upper().split(" ")[0]
    con=connect()
    exact=con.execute("""
      SELECT price,transfer_date,postcode,property_type,old_new,duration,town_city,district,county,
             source_release,fetched_at
      FROM property_transactions
      WHERE UPPER(REPLACE(postcode,' ',''))=?
      ORDER BY transfer_date DESC LIMIT ?
    """,(pc,limit)).fetchall()
    if len(exact)>=5:
        rows=exact; scope="exact_postcode"
    else:
        rows=con.execute("""
          SELECT price,transfer_date,postcode,property_type,old_new,duration,town_city,district,county,
                 source_release,fetched_at
          FROM property_transactions
          WHERE UPPER(postcode) LIKE ?
          ORDER BY transfer_date DESC LIMIT ?
        """,(outward+"%",limit)).fetchall()
        scope="outward_code"
    con.close()
    return scope,[dict(r) for r in rows]

def ons_rent_for_area(admin_district):
    con=connect()
    row=con.execute("""
      SELECT * FROM ons_rent_local_authority
      WHERE LOWER(area_name)=LOWER(?)
      ORDER BY period DESC LIMIT 1
    """,(admin_district,)).fetchone()
    if not row:
        # Conservative fuzzy fallback only removes common council suffixes.
        cleaned=(admin_district or "").replace(" City Council","").replace(" Council","").strip()
        row=con.execute("""
          SELECT * FROM ons_rent_local_authority
          WHERE LOWER(area_name)=LOWER(?)
          ORDER BY period DESC LIMIT 1
        """,(cleaned,)).fetchone()
    con.close()
    return dict(row) if row else None
