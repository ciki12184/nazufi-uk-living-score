from pathlib import Path
from db import connect
from sources import SOURCES

def main():
    con = connect()
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    con.executescript(schema)

    for key, s in SOURCES.items():
        con.execute("""
            INSERT INTO source_registry
            (source_key, publisher, title, landing_url, licence_name, attribution_text, refresh_policy, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(source_key) DO UPDATE SET
              publisher=excluded.publisher,
              title=excluded.title,
              landing_url=excluded.landing_url,
              licence_name=excluded.licence_name,
              attribution_text=excluded.attribution_text,
              refresh_policy=excluded.refresh_policy
        """, (
            key, s["publisher"], s["title"], s["landing_url"],
            s.get("licence_name"), s.get("attribution_text"), s["refresh_policy"]
        ))
        con.execute("""
            INSERT INTO dataset_publication_state(source_key, status)
            VALUES (?, 'not_yet_ingested')
            ON CONFLICT(source_key) DO NOTHING
        """, (key,))
    con.commit()
    con.close()
    print("Database initialised.")

if __name__ == "__main__":
    main()
