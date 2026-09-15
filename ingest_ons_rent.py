import json, re
from openpyxl import load_workbook
from bulk_common import download_to_staging, sha256_file, utcnow
from discover_sources import discover_latest_ons_rent_xlsx
from db import connect

def norm(v):
    return re.sub(r"\s+", " ", str(v or "").strip()).lower()

def header_score(values):
    joined = " | ".join(norm(v) for v in values)
    score = 0
    if "local authority" in joined: score += 3
    if "area code" in joined or "geography code" in joined: score += 2
    if "average monthly rent" in joined or "average rent" in joined or "rental price" in joined: score += 3
    if "annual percentage change" in joined or "annual change" in joined: score += 1
    return score

def detect_table(ws):
    # Search only the top of each sheet; if ONS changes structure materially we fail instead of guessing.
    best = None
    for r in range(1, min(ws.max_row, 60) + 1):
        vals = [ws.cell(r, c).value for c in range(1, min(ws.max_column, 80) + 1)]
        score = header_score(vals)
        if score >= 5 and (best is None or score > best[0]):
            best = (score, r, vals)
    return best

def colmap(headers):
    out = {}
    for idx, h in enumerate(headers, start=1):
        n = norm(h)
        if not n: 
            continue
        if ("area code" in n or "geography code" in n) and "area_code" not in out:
            out["area_code"] = idx
        elif ("local authority" in n or "area name" in n or "geography name" in n) and "area_name" not in out:
            out["area_name"] = idx
        elif ("average monthly rent" in n or "average rent" in n or "rental price" in n) and "rent" not in out:
            out["rent"] = idx
        elif ("annual percentage change" in n or "annual change" in n) and "annual_change" not in out:
            out["annual_change"] = idx
        elif ("month" == n or "period" in n or "date" == n) and "period" not in out:
            out["period"] = idx
    return out

def to_number(v):
    if v in (None, "", "..", ":", "-"):
        return None
    try:
        return float(str(v).replace("£","").replace(",","").replace("%","").strip())
    except Exception:
        return None

def ingest():
    info = discover_latest_ons_rent_xlsx()
    path = download_to_staging(info["url"], "ons_pipr_latest.xlsx")
    digest = sha256_file(path)
    fetched = utcnow()

    con = connect()
    prev = con.execute(
        "SELECT id FROM bulk_dataset_files WHERE source_key='ons_pipr_hpi' AND sha256=? AND is_published=1",
        (digest,)
    ).fetchone()
    if prev:
        con.close()
        return {"status":"unchanged","sha256":digest}

    wb = load_workbook(path, read_only=True, data_only=True)
    candidates = []
    for ws in wb.worksheets:
        detected = detect_table(ws)
        if detected:
            candidates.append((detected[0], ws.title, detected[1]))
    if not candidates:
        con.close()
        raise RuntimeError("ONS PIPR schema validation failed: no positively identified local-authority rent table")

    candidates.sort(reverse=True)
    _, sheet_name, header_row = candidates[0]
    ws = wb[sheet_name]
    headers = [ws.cell(header_row, c).value for c in range(1, ws.max_column + 1)]
    cm = colmap(headers)
    if not {"area_code","area_name","rent"}.issubset(cm):
        con.close()
        raise RuntimeError(f"ONS PIPR schema validation failed: detected columns {sorted(cm)}")

    # Some ONS tables may be wide-format. This parser only publishes if rows are clearly row-oriented.
    staged=[]
    for r in range(header_row+1, ws.max_row+1):
        code = ws.cell(r, cm["area_code"]).value
        name = ws.cell(r, cm["area_name"]).value
        rent = to_number(ws.cell(r, cm["rent"]).value)
        if code in (None,"") or name in (None,"") or rent is None:
            continue
        period = str(ws.cell(r, cm["period"]).value).strip() if "period" in cm else info["label"]
        annual = to_number(ws.cell(r, cm["annual_change"]).value) if "annual_change" in cm else None
        staged.append((str(code).strip(), str(name).strip(), period, rent, annual,
                       None, "ons_pipr_hpi", info["label"], fetched))

    if len(staged) < 50:
        con.close()
        raise RuntimeError(
            f"ONS PIPR validation withheld publication: only {len(staged)} row-oriented local-area records detected. "
            "Workbook structure may be wide-format or changed; no values were guessed."
        )

    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM ons_rent_local_authority")
        con.executemany("""
          INSERT INTO ons_rent_local_authority
          (area_code, area_name, period, average_monthly_rent, annual_change_pct,
           property_breakdown_json, source_key, source_release, fetched_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, staged)
        con.execute("""
          INSERT INTO bulk_dataset_files
          (source_key, discovered_url, file_name, data_period, sha256, downloaded_at,
           validation_status, row_count, is_published)
          VALUES ('ons_pipr_hpi', ?, ?, ?, ?, ?, 'validated', ?, 1)
        """, (info["url"], path.name, info["label"], digest, fetched, len(staged)))
        con.execute("""
          UPDATE dataset_publication_state
          SET status='latest_available', last_checked_at=?
          WHERE source_key='ons_pipr_hpi'
        """, (fetched,))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"status":"published","rows":len(staged),"sheet":sheet_name,"release":info["label"]}

if __name__ == "__main__":
    print(ingest())
