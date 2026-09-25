import sqlite3
from pathlib import Path

from backend.models.beneficiary import BeneficiaryProfile, Experience, Location
from backend.skill_gap.engine import SkillGapEngine, extract_official_skill_signals


def make_db(tmp_path: Path) -> Path:
    db = tmp_path / "skillgap.db"
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE qualifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            s_no INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL,
            code TEXT,
            description TEXT,
            sector_name TEXT,
            proposed_occupation TEXT
        )
    """)
    con.execute("""
        CREATE TABLE job_openings (
            job_id TEXT PRIMARY KEY, transient_id TEXT, title TEXT NOT NULL, company_name TEXT,
            description TEXT, roles_responsibility TEXT, sector_name TEXT, functional_area TEXT,
            min_education TEXT, min_experience REAL, max_experience REAL, vacancy_count INTEGER DEFAULT 0,
            min_ctc_monthly REAL, max_ctc_monthly REAL, min_ctc_annual REAL, max_ctc_annual REAL,
            wage_type TEXT, state TEXT, district TEXT, country TEXT, tags_json TEXT, posted_on TEXT,
            valid_upto TEXT, apply_url TEXT, source_system TEXT, is_active INTEGER DEFAULT 1,
            fetched_at TEXT, imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""INSERT INTO qualifications(title,code,description,sector_name,proposed_occupation)
        VALUES(?,?,?,?,?)""", (
        "Solar PV Installer Electrical", "SOLAR/1",
        "Installs, tests and commissions electrical components of photovoltaic systems while complying with safety requirements.",
        "Green Jobs", "Solar Panel Installation Technician"
    ))
    con.commit(); con.close()
    return db


def test_official_signals_are_derived_from_description_only():
    sigs = extract_official_skill_signals(
        "Installs, tests and commissions electrical components of photovoltaic systems while complying with safety requirements."
    )
    names = {s.skill for s in sigs}
    assert "installation" in names
    assert "testing" in names
    assert "commissioning" in names
    assert "safety compliance" in names
    assert "solar PV systems" in names
    assert all(s.source_type == "official_nqr_description" for s in sigs)


def test_not_evidenced_is_not_claimed_as_missing_competence(tmp_path):
    db = make_db(tmp_path)
    profile = BeneficiaryProfile(skills=["electrical safety"], occupation="electrician")
    out = SkillGapEngine(db).analyze(profile, "SOLAR/1", include_market=False)
    assert any(m.required_skill == "safety compliance" for m in out.matched_skills)
    assert "commissioning" in out.not_evidenced_skills
    assert any("not evidenced" in w for w in out.warnings)
    assert 0 <= out.profile_skill_coverage_percent <= 100


def test_generic_skill_is_only_partial_for_specialised_requirement(tmp_path):
    db = make_db(tmp_path)
    con = sqlite3.connect(db)
    con.execute("UPDATE qualifications SET description=? WHERE code='SOLAR/1'", (
        "The worker performs electrical wiring and control panel wiring, testing and transformer maintenance.",
    ))
    con.commit(); con.close()
    profile = BeneficiaryProfile(skills=["wiring"])
    out = SkillGapEngine(db).analyze(profile, "SOLAR/1", include_market=False)
    assert any(m.required_skill == "control panel wiring" and m.match_type == "partial" for m in out.partial_matches)
    assert not any(m.required_skill == "control panel wiring" for m in out.matched_skills)


def test_unknown_qualification_rejected(tmp_path):
    db = make_db(tmp_path)
    try:
        SkillGapEngine(db).analyze(BeneficiaryProfile(), "UNKNOWN", include_market=False)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Unknown qualification code" in str(exc)


def test_market_tags_are_separate_from_official_signals(tmp_path):
    db = make_db(tmp_path)
    con = sqlite3.connect(db)
    con.execute("""INSERT INTO job_openings(job_id,title,state,district,tags_json,is_active,valid_upto,source_system)
                   VALUES(?,?,?,?,?,?,?,?)""",
                ("J1", "Solar PV Installer Electrical", "Telangana", "Hyderabad",
                 '["Troubleshooting", "Wiring"]', 1, "2099-12-31T00:00:00+00:00", "NCS"))
    con.commit(); con.close()
    profile = BeneficiaryProfile(skills=["safety"], location=Location(state="Telangana", district="Hyderabad"))
    out = SkillGapEngine(db).analyze(profile, "SOLAR/1", include_market=True)
    assert "Troubleshooting" in out.market_skill_signals
    assert all(s.source_type == "official_nqr_description" for s in out.required_skill_signals)
