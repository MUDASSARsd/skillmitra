from backend.models.beneficiary import BeneficiaryProfile, Location
from backend.schemes.engine import match_schemes
from backend.schemes.store import scheme_data_status
from backend.database.db import DEFAULT_DB_PATH


def by_code(rows, code):
    return next(x for x in rows if x['scheme_code']==code)


def test_scheme_snapshot_loaded():
    s=scheme_data_status(DEFAULT_DB_PATH)
    assert s['schemes'] >= 5


def test_sc_youth_matches_pmdaksh_and_pmajay():
    p=BeneficiaryProfile(age=24, community_category='SC', location=Location(state='Telangana', district='Hyderabad'))
    rows=match_schemes(p, DEFAULT_DB_PATH)
    assert by_code(rows,'PM-DAKSH')['status']=='LIKELY_MATCH'
    assert by_code(rows,'PM-AJAY-GIA')['status']=='PROGRAM_RELEVANT'


def test_tailor_flags_vishwakarma():
    p=BeneficiaryProfile(age=30, occupation='Tailor', community_category='SC')
    row=by_code(match_schemes(p, DEFAULT_DB_PATH),'PM-VISHWAKARMA')
    assert row['status']=='POSSIBLE_MATCH'
    assert any('tailor' in r.lower() for r in row['reasons'])


def test_ddugky_outside_age_not_match():
    p=BeneficiaryProfile(age=40, area_type='rural', community_category='SC')
    assert by_code(match_schemes(p, DEFAULT_DB_PATH),'DDU-GKY')['status']=='NOT_MATCH'


def test_pmegp_self_employment_possible():
    p=BeneficiaryProfile(age=22, employment_preference='self employment', community_category='SC')
    assert by_code(match_schemes(p, DEFAULT_DB_PATH),'PMEGP')['status']=='POSSIBLE_MATCH'
