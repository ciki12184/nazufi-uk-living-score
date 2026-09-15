from pathlib import Path
import sqlite3
from config import DATABASE_PATH

DB_PATH = Path(DATABASE_PATH)

def connect():
    con = sqlite3.connect(
        DB_PATH,
        timeout=30.0,
        check_same_thread=False,
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 30000")
    con.execute("PRAGMA synchronous = NORMAL")
    return con
