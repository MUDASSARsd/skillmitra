import json
from backend.database.db import init_db
from backend.jobs.store import import_jobs_payload, search_jobs, demand_summary, jobs_data_status


def sample_payload():
    return {
      "IsSuccess": True,
      "Data": {"Jobs": {"Data": [
        {
          "Id":"uuid1","JobId":"1001","JobTitle":"Solar PV Installer","JobStatus":"Active",
          "JobDescription":"Install rooftop solar panels, inverter and wiring.","CompanyName":"Solar Co",
          "MinEduQual":"ITI","VacancyCount":"10","MinCtcMonthly":15000,"MaxCtcMonthly":25000,
          "MinCtc":"180000","MaxCtc":"300000","MinExperience":0,"MaxExperience":2,
          "Tags":"[[\"Solar PV\",\"Wiring\"]]","SourceSystem":"NCS","IsActive":True,
          "PostedOn":"2026-09-23T10:00:00Z","ValidUpto":"2026-12-01T00:00:00Z",
          "JobLocation":{"District":"Hyderabad","State":"Telangana","Country":"India"},
          "ApplyUrl":"https://example.test/1001","WageTypeDesc":"Monthly"
        },
        {
          "Id":"uuid2","JobId":"1002","JobTitle":"Solar Technician","JobStatus":"Active",
          "JobDescription":"Solar maintenance and troubleshooting.","CompanyName":"Energy Co",
          "VacancyCount":"20","MinCtcMonthly":18000,"MaxCtcMonthly":30000,
          "SearchTags":[["Solar","Troubleshooting"]],"SourceSystem":"NCS","IsActive":True,
          "PostedOn":"2026-09-22T10:00:00Z",
          "JobLocationState":"Telangana","JobLocationDistrict":"Hyderabad","JobLocationCountry":"India"
        },
        {
          "Id":"uuid3","JobId":"1003","JobTitle":"Retail Sales Executive","JobStatus":"Active",
          "VacancyCount":"5","SourceSystem":"NCS","IsActive":True,
          "JobLocation":{"District":"Hyderabad","State":"Telangana","Country":"India"}
        }
      ]}}
    }


def test_raw_ncs_shape_import_search_and_demand(tmp_path):
    db=tmp_path/'test.db'; init_db(db).close()
    result=import_jobs_payload(sample_payload(), db_path=db)
    assert result['jobs_upserted']==3
    jobs=search_jobs('solar', state='Telangana', district='Hyderabad', db_path=db)
    assert len(jobs)==2
    assert jobs[0].source_system=='NCS'
    assert 'Solar' in ' '.join(jobs[0].tags) or 'solar' in jobs[0].title.lower()
    d=demand_summary('solar', state='Telangana', district='Hyderabad', db_path=db)
    assert d.matched_job_postings==2
    assert d.total_vacancies==30
    assert d.median_monthly_salary==22000.0
    assert d.demand_band in {'MODERATE','HIGH'}
    st=jobs_data_status(db)
    assert st['active_job_openings']==3 and st['active_vacancies']==35


def test_job_import_is_idempotent(tmp_path):
    db=tmp_path/'test.db'; init_db(db).close()
    import_jobs_payload(sample_payload(), db_path=db)
    import_jobs_payload(sample_payload(), db_path=db)
    assert jobs_data_status(db)['job_openings']==3


def test_expired_jobs_are_hidden_and_location_fallback_is_explicit(tmp_path):
    from backend.jobs.store import job_evidence
    db=tmp_path/'test.db'; init_db(db).close()
    payload=sample_payload()
    payload['Data']['Jobs']['Data'].append({
        'JobId':'old1','JobTitle':'Solar Old Job','VacancyCount':'999','SourceSystem':'NCS','IsActive':True,
        'ValidUpto':'2020-01-01T00:00:00Z',
        'JobLocation':{'District':'Hyderabad','State':'Telangana','Country':'India'}
    })
    import_jobs_payload(payload, db_path=db)
    jobs=search_jobs('solar', state='Telangana', district='Hyderabad', db_path=db)
    assert all(j.job_id != 'old1' for j in jobs)
    ev=job_evidence('solar', state='Telangana', district='Warangal', db_path=db)
    assert ev['scope']=='state'
    assert ev['fallback_used'] is True
    assert len(ev['jobs'])==2


def test_relevance_prefers_title_over_description_only_match(tmp_path):
    db=tmp_path/'test.db'; init_db(db).close()
    payload=sample_payload()
    payload['Data']['Jobs']['Data'].append({
        'JobId':'noise1','JobTitle':'General Helper','JobDescription':'This document mentions solar many times solar solar solar',
        'VacancyCount':'50','SourceSystem':'NCS','IsActive':True,
        'JobLocation':{'District':'Hyderabad','State':'Telangana','Country':'India'}
    })
    import_jobs_payload(payload, db_path=db)
    jobs=search_jobs('solar pv installer', state='Telangana', district='Hyderabad', db_path=db)
    assert jobs[0].job_id=='1001'
