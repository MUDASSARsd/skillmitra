from backend.career.engine import OccupationTaxonomy, CareerProgressionEngine
from backend.database.db import DEFAULT_DB_PATH


def test_taxonomy_status_has_real_coverage():
    s=OccupationTaxonomy(DEFAULT_DB_PATH).status()
    assert s['qualifications'] >= 2800
    assert s['distinct_raw_occupation_labels'] > 1000
    assert s['qualifications_with_official_progression_text'] > 2000


def test_taxonomy_search_automotive():
    rows=OccupationTaxonomy(DEFAULT_DB_PATH).search('pipeline maintenance', limit=10)
    assert rows
    assert any('pipeline' in (x['canonical_occupation'] or '').lower() for x in rows)


def test_progression_preserves_official_text():
    out=CareerProgressionEngine(DEFAULT_DB_PATH).analyze('2020/HYC/HSSCI/3770')
    assert out['has_official_progression_text'] is True
    assert 'Senior Line Patrolling Man' in out['official_progression_text']
    assert any(x['role_text']=='Senior Line Patrolling Man' for x in out['official_progression_roles'])


def test_progression_related_are_not_claimed_official():
    out=CareerProgressionEngine(DEFAULT_DB_PATH).analyze('2021/AUT/ASDC/04347')
    for x in out['related_higher_nsqf_options']:
        assert x['relation']=='RELATED_HIGHER_NSQF_SAME_OCCUPATION_FAMILY'
        assert 'not claimed' in x['warning']
