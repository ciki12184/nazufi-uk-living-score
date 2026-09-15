def validate_postcode_record(record):
    required = ["postcode", "latitude", "longitude", "fetched_at"]
    missing = [k for k in required if record.get(k) in (None, "")]
    if missing:
        return False, f"Missing fields: {', '.join(missing)}"
    if not (-90 <= float(record["latitude"]) <= 90):
        return False, "Latitude outside valid range"
    if not (-180 <= float(record["longitude"]) <= 180):
        return False, "Longitude outside valid range"
    return True, "ok"

def validate_crime_snapshot(snapshot):
    if not snapshot.get("month"):
        return False, "Missing Police.uk data month"
    count = snapshot.get("incident_count")
    if not isinstance(count, int) or count < 0:
        return False, "Invalid incident count"
    cats = snapshot.get("categories")
    if not isinstance(cats, dict):
        return False, "Invalid category map"
    if sum(cats.values()) != count:
        return False, "Category total does not equal incident count"
    return True, "ok"

def validate_flood_check(snapshot):
    count = snapshot.get("warning_count")
    if not isinstance(count, int) or count < 0:
        return False, "Invalid flood warning count"
    return True, "ok"
