"""
Database Schema Definitions for PM-AJAY NQR & Eligibility Pipeline.
"""

CREATE_QUALIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS qualifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    s_no INTEGER NOT NULL,
    title TEXT NOT NULL,
    code TEXT,
    description TEXT,
    sector_name TEXT,
    level TEXT,
    nsqf_level_numeric REAL,
    max_notational_hours TEXT,
    min_notational_hours TEXT,
    version TEXT,
    originally_approved TEXT,
    valid_till TEXT,
    awarding_body TEXT,
    certifying_bodies TEXT,
    proposed_occupation TEXT,
    progression_pathway TEXT,
    qualification_type TEXT,
    adopted_qualification TEXT,
    training_delivery_hours TEXT,
    is_duplicate_code INTEGER DEFAULT 0,
    source_file TEXT DEFAULT 'Qualifications.xlsx',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_QUALIFICATIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_qualifications_code ON qualifications(code);
CREATE INDEX IF NOT EXISTS idx_qualifications_sector ON qualifications(sector_name);
CREATE INDEX IF NOT EXISTS idx_qualifications_level ON qualifications(nsqf_level_numeric);
"""

CREATE_QUALIFICATIONS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS qualifications_fts USING fts5(
    qualification_id UNINDEXED,
    title,
    description,
    sector_name,
    proposed_occupation,
    code,
    tokenize='porter unicode61'
);
"""

CREATE_ELIGIBILITY_ROUTES_TABLE = """
CREATE TABLE IF NOT EXISTS eligibility_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nqr_id INTEGER,
    code TEXT NOT NULL,
    route_number INTEGER NOT NULL,
    criteria_1 TEXT,
    criteria_2 TEXT,
    experience TEXT,
    experience_months INTEGER DEFAULT 0,
    training_qualification TEXT,
    source_url TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED',
    raw_text TEXT,
    fetched_at TEXT,
    source_file TEXT DEFAULT 'eligibility_routes.csv',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ELIGIBILITY_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_eligibility_code ON eligibility_routes(code);
CREATE INDEX IF NOT EXISTS idx_eligibility_nqr_id ON eligibility_routes(nqr_id);
"""

# Stubs for future datasets (Phase 13)
CREATE_TRAINING_CENTRES_STUB = """
CREATE TABLE IF NOT EXISTS training_centres (
    centre_id TEXT PRIMARY KEY,
    centre_name TEXT NOT NULL,
    state TEXT,
    district TEXT,
    address TEXT,
    latitude REAL,
    longitude REAL,
    qualification_code TEXT,
    training_partner TEXT,
    scheme TEXT,
    status TEXT
);
"""


CREATE_TRAINING_OFFERINGS_TABLE = """
CREATE TABLE IF NOT EXISTS training_offerings (
    offering_id TEXT PRIMARY KEY,
    centre_id TEXT NOT NULL,
    qualification_code TEXT,
    job_role TEXT,
    sector TEXT,
    scheme TEXT,
    batch_id TEXT,
    delivery_mode TEXT,
    batch_start_date TEXT,
    batch_end_date TEXT,
    batch_timing TEXT,
    availability_status TEXT DEFAULT 'UNKNOWN',
    source TEXT,
    source_url TEXT,
    last_verified_at TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(centre_id) REFERENCES training_centres(centre_id)
);
"""

CREATE_TRAINING_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_tc_location ON training_centres(state, district);
CREATE INDEX IF NOT EXISTS idx_to_code ON training_offerings(qualification_code);
CREATE INDEX IF NOT EXISTS idx_to_centre ON training_offerings(centre_id);
CREATE INDEX IF NOT EXISTS idx_to_job_role ON training_offerings(job_role);
"""


CREATE_JOB_OPENINGS_TABLE = """
CREATE TABLE IF NOT EXISTS job_openings (
    job_id TEXT PRIMARY KEY,
    transient_id TEXT,
    title TEXT NOT NULL,
    company_name TEXT,
    description TEXT,
    roles_responsibility TEXT,
    sector_name TEXT,
    functional_area TEXT,
    min_education TEXT,
    min_experience REAL,
    max_experience REAL,
    vacancy_count INTEGER DEFAULT 0,
    min_ctc_monthly REAL,
    max_ctc_monthly REAL,
    min_ctc_annual REAL,
    max_ctc_annual REAL,
    wage_type TEXT,
    state TEXT,
    district TEXT,
    country TEXT,
    tags_json TEXT,
    posted_on TEXT,
    valid_upto TEXT,
    apply_url TEXT,
    source_system TEXT,
    is_active INTEGER DEFAULT 1,
    fetched_at TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_JOB_OPENINGS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_jobs_location ON job_openings(state,district);
CREATE INDEX IF NOT EXISTS idx_jobs_sector ON job_openings(sector_name);
CREATE INDEX IF NOT EXISTS idx_jobs_posted ON job_openings(posted_on);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON job_openings(is_active);
"""

CREATE_SCHEMES_STUB = """
CREATE TABLE IF NOT EXISTS schemes (
    scheme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_name TEXT NOT NULL,
    ministry TEXT,
    target_beneficiary TEXT,
    age_eligibility TEXT,
    education_eligibility TEXT,
    income_eligibility TEXT,
    location_eligibility TEXT,
    benefits TEXT,
    documents TEXT,
    application_method TEXT,
    source TEXT,
    last_updated TEXT
);
"""

CREATE_LIVELIHOOD_MAPPING_STUB = """
CREATE TABLE IF NOT EXISTS livelihood_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector TEXT,
    district TEXT,
    state TEXT,
    demand_level TEXT,
    top_trades TEXT,
    average_wage REAL,
    source TEXT
);
"""


def init_db_schema(conn):
    """Executes all table creation DDLs on the provided SQLite connection."""
    with conn:
        conn.execute(CREATE_QUALIFICATIONS_TABLE)
        conn.executescript(CREATE_QUALIFICATIONS_INDEXES)
        conn.execute(CREATE_QUALIFICATIONS_FTS)
        conn.execute(CREATE_ELIGIBILITY_ROUTES_TABLE)
        conn.executescript(CREATE_ELIGIBILITY_INDEXES)
        conn.execute(CREATE_TRAINING_CENTRES_STUB)
        conn.execute(CREATE_TRAINING_OFFERINGS_TABLE)
        conn.executescript(CREATE_TRAINING_INDEXES)
        conn.execute(CREATE_JOB_OPENINGS_TABLE)
        conn.executescript(CREATE_JOB_OPENINGS_INDEXES)
        conn.execute(CREATE_SCHEMES_STUB)
        conn.execute(CREATE_LIVELIHOOD_MAPPING_STUB)
