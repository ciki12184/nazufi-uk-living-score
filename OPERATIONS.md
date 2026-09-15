# Production Operations

## Refresh policy

Daily:
- source freshness checks

Weekly:
- live postcode/crime/flood refresh for priority/cached areas

Monthly:
- Ofsted bulk refresh
- HM Land Registry PPD refresh
- ONS PIPR refresh
- school-coordinate enrichment
- re-run live source refresh

## Failure behaviour

A failed refresh must never replace valid data.

If a bulk dataset:
- cannot be downloaded,
- changes schema,
- has implausibly few records,
- fails validation,

the job stops and the existing published dataset remains active.

The public UI must display the prior source period and the refresh state.

## Monitoring

Monitor:
- `/healthz`
- `/freshness`

Alert conditions:
- database health != ok
- any monthly source status = refresh_failed
- monthly source has not been checked for 45+ days
- live source checks fail repeatedly

## Backup

Persist `/data/nazufi_living_score.db`.

Minimum recommendation:
- daily database backup
- retain 7 daily backups
- retain 3 monthly backups

## Privacy

The core postcode search does not need an account.
Do not store user IP addresses or search history unless there is a clear product need and privacy policy coverage.
