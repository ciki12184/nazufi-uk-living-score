from collectors import lookup_postcode, latest_police_month, collect_crime, collect_current_flood
from validation import validate_postcode_record, validate_crime_snapshot, validate_flood_check
from repository import save_postcode_area, save_crime, save_flood

# Prototype seed postcodes.
# Production should refresh postcodes users have searched, plus any priority locations.
SEED_POSTCODES = ["LS16 7XX", "SW1A 1AA"]

def refresh_postcode(postcode):
    area = lookup_postcode(postcode)
    ok, msg = validate_postcode_record(area)
    if not ok:
        raise RuntimeError(f"Postcode validation failed: {msg}")
    save_postcode_area(area)

    month = latest_police_month()
    crime = collect_crime(area["latitude"], area["longitude"], month)
    ok, msg = validate_crime_snapshot(crime)
    if not ok:
        raise RuntimeError(f"Crime validation failed: {msg}")
    save_crime(area["postcode"], crime)

    flood = collect_current_flood(area["latitude"], area["longitude"])
    ok, msg = validate_flood_check(flood)
    if not ok:
        raise RuntimeError(f"Flood validation failed: {msg}")
    save_flood(area["postcode"], flood)

    print(f"{area['postcode']}: refreshed using official/live sources; no generated values.")

def main():
    for postcode in SEED_POSTCODES:
        try:
            refresh_postcode(postcode)
        except Exception as e:
            # Important: failed refresh does NOT generate substitute data.
            print(f"{postcode}: refresh failed: {e}")

if __name__ == "__main__":
    main()
