from collections import Counter
from datetime import datetime, timezone
import requests

UA = "NazufiUKLivingScore/0.1 (+https://www.nazufienterprise.com/)"

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def get_json(url, timeout=30):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept": "application/json"})
    r.raise_for_status()
    return r.json()

def normalise_postcode(postcode):
    return " ".join(postcode.strip().upper().split())

def lookup_postcode(postcode):
    pc = normalise_postcode(postcode)
    data = get_json(f"https://api.postcodes.io/postcodes/{requests.utils.quote(pc)}")
    if data.get("status") != 200 or not data.get("result"):
        raise ValueError("Postcode not found")
    r = data["result"]
    return {
        "postcode": r["postcode"],
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "country": r.get("country"),
        "region": r.get("region"),
        "admin_district": r.get("admin_district"),
        "lsoa": r.get("lsoa"),
        "msoa": r.get("msoa"),
        "fetched_at": utcnow(),
    }

def latest_police_month():
    dates = get_json("https://data.police.uk/api/crimes-street-dates")
    if not dates or "date" not in dates[0]:
        raise RuntimeError("Police.uk returned no available data month")
    return dates[0]["date"]

def collect_crime(latitude, longitude, month):
    url = (
        "https://data.police.uk/api/crimes-street/all-crime"
        f"?lat={latitude}&lng={longitude}&date={month}"
    )
    crimes = get_json(url, timeout=60)
    if not isinstance(crimes, list):
        raise RuntimeError("Police.uk crime response was not a list")
    counts = Counter(c.get("category", "unknown") for c in crimes)
    return {
        "month": month,
        "incident_count": len(crimes),
        "categories": dict(counts),
        "source_url": url,
        "fetched_at": utcnow(),
    }

def collect_current_flood(latitude, longitude, distance_km=5):
    url = (
        "https://environment.data.gov.uk/flood-monitoring/id/floods"
        f"?lat={latitude}&long={longitude}&dist={distance_km}"
    )
    data = get_json(url)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise RuntimeError("Environment Agency response had unexpected shape")
    return {
        "warning_count": len(items),
        "source_url": url,
        "checked_at": utcnow(),
    }
