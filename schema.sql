PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_registry (
    source_key TEXT PRIMARY KEY,
    publisher TEXT NOT NULL,
    title TEXT NOT NULL,
    landing_url TEXT NOT NULL,
    licence_name TEXT,
    attribution_text TEXT,
    refresh_policy TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    data_period TEXT,
    published_at TEXT,
    fetched_at TEXT,
    record_count INTEGER,
    validation_message TEXT,
    source_url TEXT,
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);

CREATE TABLE IF NOT EXISTS dataset_publication_state (
    source_key TEXT PRIMARY KEY,
    last_good_run_id INTEGER,
    status TEXT NOT NULL,
    last_checked_at TEXT,
    next_expected_check TEXT,
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key),
    FOREIGN KEY (last_good_run_id) REFERENCES source_runs(id)
);

CREATE TABLE IF NOT EXISTS postcode_areas (
    postcode TEXT PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    country TEXT,
    region TEXT,
    admin_district TEXT,
    lsoa TEXT,
    msoa TEXT,
    source_key TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);

CREATE TABLE IF NOT EXISTS crime_monthly (
    postcode TEXT NOT NULL,
    data_month TEXT NOT NULL,
    incident_count INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    source_key TEXT NOT NULL,
    PRIMARY KEY (postcode, data_month),
    FOREIGN KEY (postcode) REFERENCES postcode_areas(postcode),
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);

CREATE TABLE IF NOT EXISTS crime_category_monthly (
    postcode TEXT NOT NULL,
    data_month TEXT NOT NULL,
    category TEXT NOT NULL,
    incident_count INTEGER NOT NULL,
    PRIMARY KEY (postcode, data_month, category),
    FOREIGN KEY (postcode) REFERENCES postcode_areas(postcode)
);

CREATE TABLE IF NOT EXISTS flood_live_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    postcode TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    warning_count INTEGER,
    source_key TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (postcode) REFERENCES postcode_areas(postcode),
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);


CREATE TABLE IF NOT EXISTS schools (
    urn TEXT PRIMARY KEY,
    school_name TEXT NOT NULL,
    postcode TEXT,
    local_authority TEXT,
    phase TEXT,
    latest_inspection_date TEXT,
    latest_inspection_type TEXT,
    overall_effectiveness TEXT,
    safeguarding TEXT,
    raw_json TEXT NOT NULL,
    source_key TEXT NOT NULL,
    data_period TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);

CREATE INDEX IF NOT EXISTS idx_schools_postcode ON schools(postcode);

CREATE TABLE IF NOT EXISTS property_transactions (
    transaction_id TEXT PRIMARY KEY,
    price INTEGER NOT NULL,
    transfer_date TEXT NOT NULL,
    postcode TEXT,
    property_type TEXT,
    old_new TEXT,
    duration TEXT,
    paon TEXT,
    saon TEXT,
    street TEXT,
    locality TEXT,
    town_city TEXT,
    district TEXT,
    county TEXT,
    ppd_category TEXT,
    record_status TEXT,
    source_key TEXT NOT NULL,
    source_release TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);

CREATE INDEX IF NOT EXISTS idx_ppd_postcode ON property_transactions(postcode);
CREATE INDEX IF NOT EXISTS idx_ppd_transfer_date ON property_transactions(transfer_date);

CREATE TABLE IF NOT EXISTS housing_area_summary (
    area_key TEXT NOT NULL,
    area_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    transactions INTEGER NOT NULL,
    median_price REAL,
    mean_price REAL,
    source_key TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY(area_key, area_type, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS bulk_dataset_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    discovered_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    data_period TEXT,
    published_at TEXT,
    sha256 TEXT,
    downloaded_at TEXT,
    validation_status TEXT NOT NULL,
    row_count INTEGER,
    is_published INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);


CREATE TABLE IF NOT EXISTS ons_rent_local_authority (
    area_code TEXT NOT NULL,
    area_name TEXT NOT NULL,
    period TEXT NOT NULL,
    average_monthly_rent REAL,
    annual_change_pct REAL,
    property_breakdown_json TEXT,
    source_key TEXT NOT NULL,
    source_release TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY(area_code, period),
    FOREIGN KEY (source_key) REFERENCES source_registry(source_key)
);

CREATE INDEX IF NOT EXISTS idx_ons_rent_area_name ON ons_rent_local_authority(area_name);

CREATE TABLE IF NOT EXISTS school_geography (
    urn TEXT PRIMARY KEY,
    postcode TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    geocoded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_school_geo_lat_lon ON school_geography(latitude, longitude);
