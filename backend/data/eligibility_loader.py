"""
Eligibility Routes Loader Module.
Loads, normalizes, and indexes multi-route eligibility criteria from eligibility_routes.csv into SQLite.
"""
import re
import pandas as pd
from pathlib import Path


def parse_experience_months(exp_str):
    """
    Parses experience strings into total months (INTEGER).
    e.g. '1 year' -> 12, '4 years' -> 48, '1.5 Years' -> 18, '6 months' -> 6, 'No Experience' -> 0.
    """
    if pd.isna(exp_str):
        return 0
    s = str(exp_str).strip().lower()
    if 'no experience' in s or 'none' in s or s == '':
        return 0
        
    year_match = re.search(r'([\d.]+)\s*(?:year|yr|y)', s)
    if year_match:
        try:
            years = float(year_match.group(1))
            return int(round(years * 12))
        except ValueError:
            pass
            
    month_match = re.search(r'([\d.]+)\s*(?:month|mth|m)', s)
    if month_match:
        try:
            months = float(month_match.group(1))
            return int(round(months))
        except ValueError:
            pass
            
    return 0


def clean_str(val):
    """Trims string whitespace and returns None if NaN or empty."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None




def ensure_eligibility_provenance_columns(conn):
    """Backward-compatible migration for harvested NQR provenance fields."""
    cursor = conn.cursor()
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(eligibility_routes)").fetchall()}
    additions = {
        "source_url": "TEXT",
        "verification_status": "TEXT DEFAULT 'UNVERIFIED'",
        "raw_text": "TEXT",
        "fetched_at": "TEXT",
    }
    for name, ddl in additions.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE eligibility_routes ADD COLUMN {name} {ddl}")
    conn.commit()


def load_eligibility_routes(routes_csv_path, conn):
    """
    Parses eligibility_routes.csv, computes experience in months,
    inserts into eligibility_routes table, and calculates database linkage metrics.
    
    Returns a dictionary of data quality metrics.
    """
    routes_csv_path = Path(routes_csv_path)
    if not routes_csv_path.exists():
        raise FileNotFoundError(f"Eligibility routes CSV not found at: {routes_csv_path}")

    df = pd.read_csv(routes_csv_path)
    
    ensure_eligibility_provenance_columns(conn)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM eligibility_routes;")
    
    total_routes = len(df)
    
    for idx, row in df.iterrows():
        nqr_id = row.get('nqr_id')
        try:
            nqr_id = int(nqr_id) if pd.notna(nqr_id) else None
        except (ValueError, TypeError):
            nqr_id = None

        code = clean_str(row.get('code'))
        if not code:
            continue

        route_num = row.get('route', idx + 1)
        try:
            route_num = int(route_num)
        except (ValueError, TypeError):
            route_num = idx + 1

        criteria_1 = clean_str(row.get('criteria_1'))
        criteria_2 = clean_str(row.get('criteria_2'))
        experience_raw = clean_str(row.get('experience'))
        exp_months = parse_experience_months(experience_raw)
        training_qual = clean_str(row.get('training_qualification'))
        source_url = clean_str(row.get('source_url'))
        verification_status = clean_str(row.get('verification_status')) or 'UNVERIFIED'
        raw_text = clean_str(row.get('raw_text'))
        fetched_at = clean_str(row.get('fetched_at'))

        cursor.execute("""
            INSERT INTO eligibility_routes (
                nqr_id, code, route_number, criteria_1, criteria_2,
                experience, experience_months, training_qualification,
                source_url, verification_status, raw_text, fetched_at, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nqr_id, code, route_num, criteria_1, criteria_2,
            experience_raw, exp_months, training_qual,
            source_url, verification_status, raw_text, fetched_at, routes_csv_path.name
        ))

    conn.commit()

    # Calculate data quality metrics regarding database coverage
    cursor.execute("SELECT COUNT(DISTINCT code) FROM qualifications;")
    total_qual_codes_in_db = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT q.id) 
        FROM qualifications q
        INNER JOIN eligibility_routes e ON q.code = e.code;
    """)
    quals_with_eligibility = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM qualifications;")
    total_qual_records = cursor.fetchone()[0]
    quals_without_eligibility = total_qual_records - quals_with_eligibility

    metrics = {
        "total_eligibility_routes_imported": total_routes,
        "qualifications_with_eligibility_data": quals_with_eligibility,
        "qualifications_without_eligibility_data": quals_without_eligibility,
        "eligibility_coverage_percentage": round((quals_with_eligibility / total_qual_records) * 100, 2) if total_qual_records > 0 else 0.0
    }

    return metrics
