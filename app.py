from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS, APP_ENV, ADMIN_TOKEN
from scheduler import start_scheduler, stop_scheduler
from collectors import (
    normalise_postcode,
    lookup_postcode,
    latest_police_month,
    collect_crime,
    collect_current_flood,
)
from validation import (
    validate_postcode_record,
    validate_crime_snapshot,
    validate_flood_check,
)
from repository import (
    save_postcode_area,
    save_crime,
    save_flood,
    get_area,
    get_latest_crime,
)
from db import connect

from contextlib import asynccontextmanager
import logging
import threading

logger = logging.getLogger("nazufi.app")


def _table_count(table_name: str) -> int:
    con = connect()
    try:
        row = con.execute(f"SELECT COUNT(*) AS n FROM {table_name}").fetchone()
        return int(row["n"] if row else 0)
    finally:
        con.close()


def _bootstrap_missing_bulk_data():
    try:
        schools_n = _table_count("schools")
        sales_n = _table_count("property_transactions")
        rent_n = _table_count("ons_rent_local_authority")

        if schools_n > 0 and sales_n > 0 and rent_n > 0:
            logger.info("Bulk bootstrap skipped: validated datasets already present.")
            return

        logger.info(
            "Starting initial bulk bootstrap: schools=%s sales=%s rent=%s",
            schools_n,
            sales_n,
            rent_n,
        )

        from refresh_bulk_sources import main as refresh_bulk
        from enrich_school_geography import main as enrich_schools

        refresh_bulk()
        enrich_schools()
        logger.info("Initial bulk bootstrap completed.")
    except Exception:
        logger.exception("Initial bulk bootstrap failed; no substitute data generated.")


@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    threading.Thread(
        target=_bootstrap_missing_bulk_data,
        name="nazufi-initial-bulk-bootstrap",
        daemon=True,
    ).start()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="Nazufi UK Living Score API",
    version="0.7.0",
    lifespan=lifespan,
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


def _resolve_area(postcode: str):
    pc = normalise_postcode(postcode)
    area = get_area(pc)

    if area:
        return pc, area

    fresh = lookup_postcode(pc)
    valid, message = validate_postcode_record(fresh)
    if not valid:
        raise RuntimeError(f"Postcode source validation failed: {message}")

    save_postcode_area(fresh)
    pc = fresh["postcode"]
    area = get_area(pc)

    if not area:
        raise RuntimeError("Validated postcode could not be cached")

    return pc, area


def _refresh_live_for_area(pc: str, area: dict):
    crime = get_latest_crime(pc)
    crime_error = None

    try:
        latest_month = latest_police_month()
        cached_month = crime.get("data_month") if crime else None

        if cached_month != latest_month:
            snapshot = collect_crime(
                area["latitude"],
                area["longitude"],
                latest_month,
            )

            ok, message = validate_crime_snapshot(snapshot)
            if not ok:
                raise RuntimeError(f"Police.uk validation failed: {message}")

            save_crime(pc, snapshot)
            crime = get_latest_crime(pc)

    except Exception as exc:
        crime_error = str(exc)
        logger.warning("Police.uk refresh failed for %s: %s", pc, exc)

    flood = None
    flood_error = None

    try:
        snapshot = collect_current_flood(
            area["latitude"],
            area["longitude"],
        )

        ok, message = validate_flood_check(snapshot)
        if not ok:
            raise RuntimeError(f"Environment Agency validation failed: {message}")

        save_flood(pc, snapshot)

        flood = {
            "status": "latest_available",
            "warning_count": snapshot["warning_count"],
            "checked_at": snapshot["checked_at"],
            "source_url": snapshot["source_url"],
            "scope": "current flood alerts/warnings only",
        }

    except Exception as exc:
        flood_error = str(exc)
        logger.warning(
            "Environment Agency refresh failed for %s: %s",
            pc,
            exc,
        )

    if not crime:
        crime = {
            "status": "unavailable",
            "message": "Police.uk data could not be retrieved from the source.",
            "source_error": crime_error,
        }
    else:
        crime["status"] = "latest_available"

    if not flood:
        flood = {
            "status": "unavailable",
            "message": "Current Environment Agency flood data could not be retrieved.",
            "source_error": flood_error,
            "scope": "current flood alerts/warnings only",
        }

    return crime, flood


@app.get("/")
def root():
    return {
        "service": "Nazufi UK Living Score API",
        "status": "ok",
        "version": "0.7.0",
        "data_policy": "No source -> no score. No data -> no AI guess.",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_policy": "No source -> no score. No data -> no AI guess.",
    }


@app.get("/sources")
def sources():
    return {"sources": sources_for_api()}


@app.get("/postcode/{postcode}")
def postcode_view(postcode: str):
    try:
        pc, area = _resolve_area(postcode)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Postcode unavailable from source: {exc}",
        )

    crime, flood = _refresh_live_for_area(pc, area)

    return {
        "postcode": pc,
        "area": area,
        "crime": crime,
        "current_flood_context": flood,
        "education": {
            "status": (
                "latest_available"
                if _table_count("schools") > 0
                else "update_pending"
            ),
            "message": "Ofsted bulk data is loaded separately and never AI-filled.",
        },
        "housing": {
            "status": (
                "latest_available"
                if _table_count("property_transactions") > 0
                else "update_pending"
            ),
            "message": "HM Land Registry bulk data is loaded separately and never AI-filled.",
        },
        "score": {
            "status": "withheld",
            "message": (
                "No score is published until all required source metrics "
                "and comparison baselines are validated."
            ),
        },
        "sources": sources_for_api(),
    }


@app.get("/schools/{postcode}")
def schools_near_postcode(postcode: str):
    pc = normalise_postcode(postcode)

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
        "note": (
            "No school is invented or distance-estimated. "
            "Exact-postcode results only until validated coordinates are added."
        ),
    }


@app.get("/property-sales/{postcode}")
def property_sales(postcode: str):
    pc = normalise_postcode(postcode)

    con = connect()
    rows = con.execute("""
      SELECT transaction_id, price, transfer_date, postcode, property_type,
             old_new, duration, town_city, district, county,
             source_release, fetched_at
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
        "attribution": (
            "Contains HM Land Registry data © Crown copyright and database right 2021. "
            "This data is licensed under the Open Government Licence v3.0."
        ),
        "warning": (
            "Recent Price Paid Data can be incomplete because registration "
            "follows transactions. Current-month data must not be treated alone "
            "as final market-volume evidence."
        ),
    }


from area_service import nearby_schools, property_sales_prefix, ons_rent_for_area


@app.get("/area-report/{postcode}")
def area_report(postcode: str):
    try:
        pc, area = _resolve_area(postcode)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Postcode unavailable from source: {exc}",
        )

    crime, flood = _refresh_live_for_area(pc, area)

    schools = nearby_schools(
        area["latitude"],
        area["longitude"],
        max_km=3.0,
        limit=12,
    )

    sale_scope, sales = property_sales_prefix(pc, limit=25)
    rent = ons_rent_for_area(area.get("admin_district"))

    schools_loaded = _table_count("schools") > 0
    sales_loaded = _table_count("property_transactions") > 0
    rent_loaded = _table_count("ons_rent_local_authority") > 0

    return {
        "postcode": pc,
        "area": area,
        "crime": crime,
        "current_flood_context": flood,
        "schools": {
            "status": (
                "latest_available"
                if schools
                else ("unavailable" if schools_loaded else "update_pending")
            ),
            "radius_km": 3.0,
            "items": schools,
            "message": (
                None
                if schools
                else (
                    "No matching Ofsted schools were found within the validated radius."
                    if schools_loaded
                    else "Ofsted dataset ingestion is currently pending."
                )
            ),
        },
        "property_sales": {
            "status": (
                "latest_available"
                if sales
                else ("unavailable" if sales_loaded else "update_pending")
            ),
            "scope": sale_scope,
            "items": sales,
            "attribution": (
                "Contains HM Land Registry data © Crown copyright and database right 2021. "
                "This data is licensed under the Open Government Licence v3.0."
            ),
            "message": (
                None
                if sales
                else (
                    "No matching transactions were found in the currently "
                    "published Price Paid Data scope."
                    if sales_loaded
                    else "HM Land Registry dataset ingestion is currently pending."
                )
            ),
        },
        "private_rent": {
            "status": (
                "latest_available"
                if rent
                else ("unavailable" if rent_loaded else "update_pending")
            ),
            "geography": "local_authority",
            "item": rent,
            "message": (
                None
                if rent
                else (
                    "No matching ONS local-authority rent row was found."
                    if rent_loaded
                    else "ONS private-rent dataset ingestion is currently pending."
                )
            ),
        },
        "overall_score": {
            "status": "withheld",
            "reason": (
                "Nazufi does not publish a combined score until every included "
                "metric has a published formula, benchmark and validated source."
            ),
        },
        "data_policy": "No source -> no score. No data -> no AI guess.",
    }


@app.get("/freshness")
def freshness():
    con = connect()
    rows = con.execute("""
      SELECT s.source_key, s.publisher, s.title, s.refresh_policy,
             p.status, p.last_checked_at, p.next_expected_check,
             r.data_period, r.published_at, r.fetched_at,
             r.validation_message
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
        "dataset_counts": {
            "schools": _table_count("schools"),
            "property_transactions": _table_count("property_transactions"),
            "ons_rent_local_authority": _table_count("ons_rent_local_authority"),
        },
        "policy": "No source -> no score. No data -> no AI guess.",
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

    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
    }


def _require_admin(authorization: str | None):
    if not ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Admin refresh is not configured.",
        )

    expected = f"Bearer {ADMIN_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="Unauthorised.",
        )


@app.post("/admin/refresh/live")
def admin_refresh_live(
    authorization: str | None = Header(default=None),
):
    _require_admin(authorization)

    from refresh_live_sources import main as refresh_live

    refresh_live()

    return {
        "ok": True,
        "job": "refresh_live",
    }


@app.post("/admin/refresh/bulk")
def admin_refresh_bulk(
    authorization: str | None = Header(default=None),
):
    _require_admin(authorization)

    from refresh_bulk_sources import main as refresh_bulk
    from enrich_school_geography import main as enrich_schools

    refresh_bulk()
    enrich_schools()

    return {
        "ok": True,
        "job": "refresh_bulk_and_school_geography",
    }
