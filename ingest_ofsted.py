import csv
import io
import json
import re

from bulk_common import download_to_staging, sha256_file, utcnow
from discover_sources import discover_latest_ofsted_csv
from db import connect


def clean(v):
    return (v or "").strip()


def normalise_key(k):
    return re.sub(r"[^a-z0-9]+", "_", (k or "").strip().lower()).strip("_")


def find_field(row, aliases):
    normalised = {normalise_key(k): v for k, v in row.items()}
    for alias in aliases:
        if alias in normalised:
            return clean(normalised[alias])
    return ""


def validate_headers(headers):
    keys = {normalise_key(h) for h in headers}
    must_have_groups = [
        {"urn"},
        {"school_name", "provider_name", "establishment_name"},
        {"postcode"},
    ]
    for group in must_have_groups:
        if not (keys & group):
            return False, f"Missing expected field group: {sorted(group)}"
    return True, "ok"


def load_ofsted_text(path):
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "cp1252"


def ingest():
    info = discover_latest_ofsted_csv()
    path = download_to_staging(info["url"], "ofsted_latest.csv")
    digest = sha256_file(path)
    fetched = utcnow()

    con = connect()
    existing = con.execute(
        """
        SELECT id
        FROM bulk_dataset_files
        WHERE source_key='ofsted_schools'
          AND sha256=?
          AND is_published=1
        """,
        (digest,),
    ).fetchone()

    if existing:
        con.close()
        return {"status": "unchanged", "sha256": digest}

    text, encoding_used = load_ofsted_text(path)
    reader = csv.DictReader(io.StringIO(text))

    ok, msg = validate_headers(reader.fieldnames or [])
    if not ok:
        con.close()
        raise RuntimeError(f"Ofsted schema validation failed: {msg}")

    staged = []

    for row in reader:
        urn = find_field(row, ["urn"])
        name = find_field(
            row,
            ["school_name", "provider_name", "establishment_name"],
        )
        postcode = find_field(row, ["postcode"])

        if not urn or not name:
            continue

        staged.append(
            (
                urn,
                name,
                postcode,
                find_field(row, ["local_authority", "la_name"]),
                find_field(row, ["phase_of_education", "phase"]),
                find_field(
                    row,
                    [
                        "inspection_end_date",
                        "inspection_date",
                        "latest_inspection_date",
                    ],
                ),
                find_field(row, ["inspection_type"]),
                find_field(
                    row,
                    ["overall_effectiveness", "overall_effectiveness_grade"],
                ),
                find_field(
                    row,
                    ["safeguarding", "safeguarding_is_effective"],
                ),
                json.dumps(row, ensure_ascii=False),
                "ofsted_schools",
                info["label"],
                fetched,
            )
        )

    if len(staged) < 1000:
        con.close()
        raise RuntimeError(
            f"Ofsted row-count validation failed: only {len(staged)} usable rows"
        )

    con.execute("BEGIN")

    try:
        con.execute("DELETE FROM schools")

        con.executemany(
            """
            INSERT INTO schools
            (
                urn,
                school_name,
                postcode,
                local_authority,
                phase,
                latest_inspection_date,
                latest_inspection_type,
                overall_effectiveness,
                safeguarding,
                raw_json,
                source_key,
                data_period,
                fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            staged,
        )

        con.execute(
            """
            INSERT INTO bulk_dataset_files
            (
                source_key,
                discovered_url,
                file_name,
                data_period,
                sha256,
                downloaded_at,
                validation_status,
                row_count,
                is_published
            )
            VALUES ('ofsted_schools', ?, ?, ?, ?, ?, 'validated', ?, 1)
            """,
            (
                info["url"],
                path.name,
                info["label"],
                digest,
                fetched,
                len(staged),
            ),
        )

        con.execute(
            """
            UPDATE dataset_publication_state
            SET status='latest_available',
                last_checked_at=?
            WHERE source_key='ofsted_schools'
            """,
            (fetched,),
        )

        con.commit()

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()

    return {
        "status": "published",
        "rows": len(staged),
        "sha256": digest,
        "label": info["label"],
        "encoding": encoding_used,
    }


if __name__ == "__main__":
    print(ingest())
