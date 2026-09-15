from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS, APP_ENV, ADMIN_TOKEN
from scheduler import start_scheduler, stop_scheduler
from collectors import normalise_postcode, lookup_postcode
from validation import validate_postcode_record
from repository import save_postcode_area, get_area, get_latest_crime
from db import connect

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()

app = FastAPI(
    title="Nazufi UK Living Score API",
    version="0.6.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

def sources_for_api():
    con = connect()
    rows = con.execute("""
      SELECT s.source_key, s.publisher, s.title, s.landing_url, s.licence_name,
             s.attribution_text, s.refresh_policy,
             p.status, p.last_checked_at
      FROM source_registry s
      LEFT JOIN dataset_publication_state p ON p.source_key=s.source_key
      WHERE s.enabled=1
      ORDER BY s.source_key
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_policy": "No source -> no score. No data -> no AI guess."
    }

@app.get("/sources")
def sources():
    return {"sources": sources_for_api()}

@app.get("/postcode/{postcode}")
def postcode_view(postcode: str):
    pc = normalise_postcode(postcode)

    # Resolve live geography if postcode isn't cached.
    area = get_area(pc)
    if not area:
        try:
            fresh = lookup_postcode(pc)
            valid, message = validate_postcode_record(fresh)
            if not valid:
                raise HTTPException(status_code=502, detail=f"Source validation failed: {message}")
            save_postcode_area(fresh)
            area = get_area(fresh["postcode"])
            pc = fresh["postcode"]
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Postcode unavailable from source: {exc}")

    crime = get_latest_crime(pc)

    return {
        "postcode": pc,
        "area": area,
        "crime": crime if crime else {
            "status": "unavailable",
            "message": "No validated Police.uk snapshot has been ingested for this postcode."
        },
        "education": {
            "status": "not_yet_ingested",
            "message": "No AI or inferred value is substituted."
        },
        "housing": {
            "status": "not_yet_ingested",
            "message": "No AI or inferred value is substituted."
        },
        "long_term_flood_risk": {
            "status": "not_yet_ingested",
            "message": "No AI or inferred value is substituted."
        },
        "score": {
            "status": "withheld",
            "message": "No score is published until all required source metrics and comparison baselines are validated."
        },
        "sources": sources_for_api()
    }


@app.get("/schools/{postcode}")
def schools_near_postcode(postcode: str):
    pc = normalise_postcode(postcode)
    # Exact postcode first. Distance-ranking requires school coordinates, which will be added
    # only from a traceable official geography source; it is not guessed.
    con = connect()
    rows = con.execute("""
      SELECT urn, school_name, postcode, local_authority, phase,
             latest_inspection_date, latest_inspection_type,
             overall_effectiveness, safeguarding, data_period, fetched_at
      FROM schools
      WHERE UPPER(REPLACE(postcode,' ','')) = UPPER(REPLACE(?,' ',''))
      ORDER BY school_name
    """, (pc,)).fetchall()
    con.close()
    return {
        "postcode": pc,
        "status": "latest_available" if rows else "unavailable",
        "schools": [dict(r) for r in rows],
        "note": "No school is invented or distance-estimated. Exact-postcode results only until validated coordinates are added."
    }

@app.get("/property-sales/{postcode}")
def property_sales(postcode: str):
    pc = normalise_postcode(postcode)
    con = connect()
    rows = con.execute("""
      SELECT transaction_id, price, transfer_date, postcode, property_type,
             old_new, duration, town_city, district, county, source_release, fetched_at
      FROM property_transactions
      WHERE UPPER(REPLACE(postcode,' ','')) = UPPER(REPLACE(?,' ',''))
      ORDER BY transfer_date DESC, price DESC
      LIMIT 100
    """, (pc,)).fetchall()
    con.close()
    return {
        "postcode": pc,
        "status": "latest_available" if rows else "unavailable",
        "transactions": [dict(r) for r in rows],
        "attribution": "Contains HM Land Registry data © Crown copyright and database right 2021. This data is licensed under the Open Government Licence v3.0.",
        "warning": "Recent Price Paid Data can be incomplete because registration follows transactions. Current-month data must not be treated alone as final market-volume evidence."
    }


from area_service import nearby_schools, property_sales_prefix, ons_rent_for_area

@app.get("/area-report/{postcode}")
def area_report(postcode: str):
    pc = normalise_postcode(postcode)
    area = get_area(pc)
    if not area:
        try:
            fresh = lookup_postcode(pc)
            valid, message = validate_postcode_record(fresh)
            if not valid:
                raise HTTPException(status_code=502, detail=f"Source validation failed: {message}")
            save_postcode_area(fresh)
            area = get_area(fresh["postcode"])
            pc = fresh["postcode"]
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Postcode unavailable from source: {exc}")

    crime = get_latest_crime(pc)
    schools = nearby_schools(area["latitude"], area["longitude"], max_km=3.0, limit=12)
    sale_scope, sales = property_sales_prefix(pc, limit=25)
    rent = ons_rent_for_area(area.get("admin_district"))

    return {
        "postcode": pc,
        "area": area,
        "crime": crime if crime else {"status":"unavailable"},
        "schools": {
            "status":"latest_available" if schools else "unavailable",
            "radius_km":3.0,
            "items":schools
        },
        "property_sales": {
            "status":"latest_available" if sales else "unavailable",
            "scope":sale_scope,
            "items":sales,
            "attribution":"Contains HM Land Registry data © Crown copyright and database right 2021. This data is licensed under the Open Government Licence v3.0."
        },
        "private_rent": {
            "status":"latest_available" if rent else "unavailable",
            "geography":"local_authority",
            "item":rent
        },
        "overall_score":{
            "status":"withheld",
            "reason":"Nazufi does not publish a combined score until every included metric has a published formula, benchmark and validated source."
        },
        "data_policy":"No source -> no score. No data -> no AI guess."
    }


@app.get("/freshness")
def freshness():
    con = connect()
    rows = con.execute("""
      SELECT s.source_key, s.publisher, s.title, s.refresh_policy,
             p.status, p.last_checked_at, p.next_expected_check,
             r.data_period, r.published_at, r.fetched_at, r.validation_message
      FROM source_registry s
      LEFT JOIN dataset_publication_state p ON p.source_key=s.source_key
      LEFT JOIN source_runs r ON r.id=p.last_good_run_id
      WHERE s.enabled=1
      ORDER BY s.source_key
    """).fetchall()
    con.close()
    return {
        "environment": APP_ENV,
        "sources": [dict(r) for r in rows],
        "policy": "No source -> no score. No data -> no AI guess."
    }

@app.get("/healthz")
def healthz():
    con = connect()
    try:
        con.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        con.close()
    return {"status":"ok" if db_ok else "degraded","database":db_ok}


def _require_admin(authorization: str | None):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin refresh is not configured.")
    expected = f"Bearer {ADMIN_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorised.")

@app.post("/admin/refresh/live")
def admin_refresh_live(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from refresh_live_sources import main as refresh_live
    refresh_live()
    return {"ok": True, "job": "refresh_live"}

@app.post("/admin/refresh/bulk")
def admin_refresh_bulk(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from refresh_bulk_sources import main as refresh_bulk
    from enrich_school_geography import main as enrich_schools
    refresh_bulk()
    enrich_schools()
    return {"ok": True, "job": "refresh_bulk_and_school_geography"}
