# Nazufi UK Living Score — Deployment v6

## Recommended beta architecture

One long-running API service:
- FastAPI
- SQLite on a persistent disk
- internal APScheduler
- Wix/Velo calls the API over HTTPS

This avoids sharing one SQLite file between separate web and cron services.

## Render

The included `render.yaml` defines:
- one Docker web service
- `/healthz` health check
- 5 GB persistent disk mounted at `/data`
- production origin allowlist
- generated admin token

After deploy:
1. Copy the public HTTPS service URL.
2. Open `wix_velo/livingScore.web.js`.
3. Replace `https://YOUR-API-DOMAIN.example` with the service URL.
4. Test `/healthz`.
5. Test `/freshness`.
6. Run one protected bulk refresh if desired.
7. Connect the Wix page.

## Railway

The included `railway.toml` uses the Dockerfile and `/healthz`.

In Railway:
1. Create a service from the project/repository.
2. Add a persistent Volume mounted at `/data`.
3. Set:
   - `APP_ENV=production`
   - `DATABASE_PATH=/data/nazufi_living_score.db`
   - `ALLOWED_ORIGINS=https://www.nazufienterprise.com,https://nazufienterprise.com`
   - `ADMIN_TOKEN=<long-random-secret>`
4. Generate a public domain.
5. Replace the Wix `API_BASE` with that domain.

## Internal scheduler

UTC schedules:
- Daily 04:15 — source freshness check
- Sunday 04:40 — live-source refresh
- 22nd of each month 05:10 — bulk refresh → school geocoding → live refresh

Each collector still checks the source's actual newest release.

## Why not a separate cron service for this SQLite beta?

Separate services generally do not share the same local filesystem/volume.
For the beta, keeping the scheduler inside the single web service ensures the API
and update pipeline use the same persistent SQLite database.

If the product scales, migrate the data store to PostgreSQL. At that point,
web and scheduled workers can be separated cleanly.

## Manual refresh

Protected endpoints:
- `POST /admin/refresh/live`
- `POST /admin/refresh/bulk`

Header:
`Authorization: Bearer <ADMIN_TOKEN>`

Never expose `ADMIN_TOKEN` in Wix page code. It is for operator use only.
