# Nazufi UK Living Score — Open Data Backend v1

This backend is the foundation for the Nazufi UK Living Score data pipeline.

## Core rule

**No source → No score. No data → No AI guess.**

The backend stores:
- source publisher
- source URL
- data period
- published date when available
- Nazufi fetch timestamp
- validation status
- last-known-good status
- source attribution

The public API must never replace missing official data with generated or inferred values.

## Current live connectors

1. Postcodes.io
   - postcode geography
   - latitude / longitude
   - local authority
   - LSOA / MSOA
2. Police.uk
   - latest available month
   - street-level crime categories
3. Environment Agency flood monitoring
   - current flood warnings/alerts near coordinates

## Open-data ingestion registry

The registry also tracks:
- Ofsted school inspection datasets
- HM Land Registry Price Paid Data
- ONS private rent and house price releases
- Environment Agency long-term flood-risk data

These bulk datasets should be downloaded, validated and indexed locally before being exposed to the postcode-search API.

## Why bulk data is stored locally

Government datasets such as Ofsted and HM Land Registry are often published as CSV/ODS bulk files rather than small postcode APIs. Querying a large public file on every user request would be slow and unreliable.

The intended production flow is:

Official source
→ collector
→ staging table/file
→ validation
→ publish as last-known-good
→ derived metrics
→ postcode API
→ Nazufi frontend

## Suggested schedules

- Police.uk: monthly check
- Ofsted: monthly check
- HM Land Registry Price Paid Data: monthly check after official release
- ONS PIPR/HPI: monthly check after official release
- Postcode geography: quarterly
- Environment Agency current warnings: live request
- Long-term flood-risk bulk data: check monthly for a newer release

The code does not hard-code a made-up publication date. It records what the source actually returns or what the ingestion job establishes.

## Database

SQLite is used for the prototype. Production can move to PostgreSQL without changing the data principles.

Important tables:
- `source_registry`
- `source_runs`
- `postcode_areas`
- `crime_monthly`
- `crime_category_monthly`
- `flood_live_checks`
- `dataset_publication_state`

## Local run

```bash
python -m pip install -r requirements.txt
python init_db.py
python refresh_live_sources.py
uvicorn app:app --reload
```

Then:

`GET /postcode/LS16%207XX`

## Automated refresh

Example cron pattern:

```cron
# Daily source freshness check at 04:15
15 4 * * * cd /app && python source_freshness_check.py

# Monthly crime refresh on the 5th at 04:40
40 4 5 * * cd /app && python refresh_live_sources.py
```

In production, use the hosting platform's scheduler rather than relying on a user's browser being open.

## Safety and transparency

The API returns `source_status` and source metadata with every dataset.

If validation fails:
- the new dataset is not published
- the prior last-known-good dataset remains available
- status becomes `refresh_failed` or `update_pending`

If there is no valid prior dataset:
- the API returns `unavailable`
- no substitute value is generated

## HM Land Registry attribution

Where Price Paid Data is used, display the attribution required by the source:

> Contains HM Land Registry data © Crown copyright and database right 2021. This data is licensed under the Open Government Licence v3.0.

Do not assume all fields in a public dataset have identical reuse conditions; review current source terms before production deployment.


## v2 bulk ingestion

Run:

```bash
python init_db.py
python refresh_bulk_sources.py
```

This automatically:
- discovers the newest Ofsted "latest inspections" CSV from GOV.UK
- downloads and validates it
- discovers the HM Land Registry current-month PPD CSV
- downloads and validates it
- checks the current ONS housing/rent release page
- publishes new database data only after validation passes

New API endpoints:
- `GET /schools/{postcode}`
- `GET /property-sales/{postcode}`

### Important HMLR limitation

The two most recent Price Paid Data months can be incomplete because registration can lag the sale.
Nazufi must show this caveat and must not interpret current-month transaction volume as a complete market measure.

### Important Ofsted limitation

Inspection frameworks and grading fields can change over time.
The ingester stores the full source row as JSON as well as selected display fields.
If expected identifying columns disappear, publication fails instead of guessing a new schema.


## v3 integrated postcode report

New components:
- `ingest_ons_rent.py`
- `enrich_school_geography.py`
- `area_service.py`
- `frontend_integrated_beta.html`
- `GET /area-report/{postcode}`

Recommended refresh order:

```bash
python init_db.py
python refresh_bulk_sources.py
python enrich_school_geography.py
python refresh_live_sources.py
uvicorn app:app --host 0.0.0.0 --port 8000
```

### ONS PIPR safeguard

The ONS workbook parser is deliberately conservative. If it cannot positively identify a
row-oriented local-authority rent table with the expected identifying fields, it fails
publication and leaves previous valid data untouched. It does **not** guess which columns
contain rent values.

ONS notes that local-authority estimates can be volatile when collection volumes are low.
Nazufi should therefore display these estimates as area context and avoid over-interpreting
single-month changes.

### Frontend

Open `frontend_integrated_beta.html` after setting `API_BASE` to the deployed API URL.

For production, restrict CORS to the Nazufi domain rather than `*`.


## v4 production layer

Added:
- Dockerfile
- docker-compose.yml
- environment-variable configuration
- production CORS allowlist
- `/healthz`
- `/freshness`
- daily / weekly / monthly refresh scripts
- Wix integration guide
- operations guide
- public source-status dashboard
- production frontend preview

This version is ready to deploy to any container host that supports:
- persistent storage
- HTTPS
- scheduled jobs

The host is an infrastructure choice only. The data policy remains unchanged.


## v5 Wix-native integration package

Folder: `wix_velo/`

Contains:
- `livingScore.web.js` — modern Velo backend web module
- `page-code.js` — page interaction and result rendering
- `ELEMENT_IDS.md` — exact Wix element IDs
- `WIX_NATIVE_ARCHITECTURE.md` — deployment flow

Nazufi's current Wix site has Velo enabled, so this is the preferred website integration path after the backend obtains a public HTTPS URL.


## v6 deployment-ready beta

Added:
- internal APScheduler for recurring data refresh
- Render Blueprint (`render.yaml`)
- Railway config (`railway.toml`)
- persistent SQLite deployment architecture
- protected operator refresh endpoints
- deployment guide

This beta intentionally runs a single application replica because the scheduler
and SQLite database live inside the same service. Migrate to PostgreSQL before
horizontal scaling.
