"""
NQR Qualifications Loader Module.
Loads, cleans, normalizes, and indexes NQR qualifications from Qualifications.xlsx into SQLite.
"""
import re
import pandas as pd
from pathlib import Path


def parse_numeric_level(level_val):
    """Extracts numeric float value from NSQF Level string (e.g. 'Level 3.5' -> 3.5)."""
    if pd.isna(level_val):
        return None
    val_str = str(level_val).strip()
    match = re.search(r'[\d.]+', val_str)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def clean_str(val):
    """Trims string whitespace and returns None if NaN or empty."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def load_nqr_qualifications(excel_path, conn):
    """
    Parses Qualifications.xlsx, normalizes fields, detects duplicate codes,
    populates qualifications table and FTS5 search index.
    
    Returns a dictionary of data quality metrics.
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found at: {excel_path}")
        
    df = pd.read_excel(excel_path, header=2)
    
    total_records = len(df)
    
    # Extract codes and identify nulls & duplicates
    raw_codes = df['Code'].apply(clean_str)
    
    null_code_mask = raw_codes.isna()
    null_code_count = int(null_code_mask.sum())
    
    # Identify non-null code frequencies to find duplicates
    code_counts = raw_codes.dropna().value_counts()
    duplicate_code_set = set(code_counts[code_counts > 1].index)
    duplicate_record_count = int(raw_codes.isin(duplicate_code_set).sum())
    unique_code_count = int(raw_codes.dropna().nunique())

    qualifications_to_insert = []
    fts_entries_to_insert = []

    cursor = conn.cursor()
    cursor.execute("DELETE FROM qualifications;")
    cursor.execute("DELETE FROM qualifications_fts;")

    for idx, row in df.iterrows():
        s_no = int(row.get('S No.', idx + 1))
        title = clean_str(row.get('Title')) or f"Untitled Qualification {s_no}"
        code = clean_str(row.get('Code'))
        description = clean_str(row.get('Description'))
        sector_name = clean_str(row.get('Sector Name'))
        level_raw = clean_str(row.get('Level'))
        numeric_level = parse_numeric_level(level_raw)
        
        max_hours = clean_str(row.get('Maximum Notational Hours'))
        min_hours = clean_str(row.get('Minimum Notational Hours'))
        version = clean_str(row.get('Version'))
        originally_approved = clean_str(row.get('Originally Approved'))
        valid_till = clean_str(row.get('Valid Till'))
        awarding_body = clean_str(row.get('Awarding Body'))
        certifying_bodies = clean_str(row.get('Certifying Bodies'))
        proposed_occupation = clean_str(row.get('Proposed Occupation'))
        progression_pathway = clean_str(row.get('Progression Pathway'))
        qualification_type = clean_str(row.get('Qualifcation Type'))  # Note spelling in Excel
        adopted_qualification = clean_str(row.get('Adopted Qualifcation'))
        training_delivery_hours = clean_str(row.get('Training Delivery Hours'))

        is_duplicate = 1 if (code and code in duplicate_code_set) else 0

        cursor.execute("""
            INSERT INTO qualifications (
                s_no, title, code, description, sector_name, level, nsqf_level_numeric,
                max_notational_hours, min_notational_hours, version, originally_approved,
                valid_till, awarding_body, certifying_bodies, proposed_occupation,
                progression_pathway, qualification_type, adopted_qualification,
                training_delivery_hours, is_duplicate_code, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s_no, title, code, description, sector_name, level_raw, numeric_level,
            max_hours, min_hours, version, originally_approved, valid_till,
            awarding_body, certifying_bodies, proposed_occupation,
            progression_pathway, qualification_type, adopted_qualification,
            training_delivery_hours, is_duplicate, excel_path.name
        ))

        qual_id = cursor.lastrowid

        # Insert into FTS search table
        cursor.execute("""
            INSERT INTO qualifications_fts (
                qualification_id, title, description, sector_name, proposed_occupation, code
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(qual_id),
            title or "",
            description or "",
            sector_name or "",
            proposed_occupation or "",
            code or ""
        ))

    conn.commit()

    metrics = {
        "total_qualification_records": total_records,
        "unique_qualification_codes": unique_code_count,
        "duplicate_code_values": list(duplicate_code_set),
        "duplicate_code_records_count": duplicate_record_count,
        "null_code_records_count": null_code_count
    }
    
    return metrics
