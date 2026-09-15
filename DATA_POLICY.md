# Nazufi UK Living Score Data Policy

## Immutable product rules

1. **No source → No score.**
2. **No data → No AI guess.**
3. AI must not invent, interpolate or silently fill numerical gaps.
4. Official/source values and Nazufi-derived values must be visibly separated.
5. A Nazufi-derived metric must disclose:
   - inputs
   - source
   - formula
   - weighting
   - comparison baseline
   - data period
6. Missing values remain missing.
7. Failed refreshes do not overwrite the last-known-good dataset.
8. A stale source is labelled stale/pending; it is not presented as newly current.
9. Paid/proprietary datasets are not part of the core Living Score.
10. Open-data licence and attribution requirements are retained in the UI and documentation.

## Allowed transformation

Nazufi may:
- normalise units
- aggregate official records
- calculate rates
- calculate percentiles
- compare an area with a defined benchmark
- calculate a published score

Only when the source data and formula are both traceable.

## Not allowed

Nazufi must not:
- ask an LLM to estimate crime counts
- invent school ratings
- invent house prices or rents
- infer flood risk when official data is absent
- replace a failed API call with a plausible number
- hide that data are older than the latest expected release

## Output states

Every metric must be one of:
- `live`
- `latest_available`
- `last_known_good`
- `update_pending`
- `refresh_failed`
- `unavailable`
- `not_yet_ingested`

A numerical value must never be shown in the last two states.
