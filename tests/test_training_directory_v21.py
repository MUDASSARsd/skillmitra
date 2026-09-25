from backend.database.db import init_db
from backend.training.directory import parse_kaushal_bharat_html, upsert_directory_centres, find_directory_centres, directory_status
from backend.training.store import training_data_status


def test_parse_official_directory_table_and_safe_batch_semantics(tmp_path):
    html='''<html><body><p>The report is generated based on data available in Kaushal Bharat as of 23-Sep-2026.</p>
    <table><tr><th>S.No.</th><th>StateName</th><th>Sanction Order</th><th>PIA</th><th>TC Name</th><th>TC ID</th><th>Batch Count</th><th>Candidate Enrolled</th><th>Candidate Freezed</th><th>Trained</th><th>Dropout</th><th>Undergoing</th><th>Assessed</th><th>Certified</th><th>Appointed</th><th>Monthly Continuity</th><th>Placed</th></tr>
    <tr><td>1</td><td>TELANGANA</td><td>SO-1</td><td>PARTNER</td><td>Centre A</td><td>1001</td><td>7</td><td>100</td><td>100</td><td>80</td><td>5</td><td>15</td><td>70</td><td>60</td><td>50</td><td>40</td><td>30</td></tr></table></body></html>'''
    recs=parse_kaushal_bharat_html(html,'https://example.test/report')
    assert len(recs)==1
    assert recs[0]['reported_batch_count']==7
    assert recs[0]['candidate_undergoing']==15
    assert recs[0]['directory_as_of']=='2026-09-23'
    db=tmp_path/'t.db'; init_db(db).close()
    upsert_directory_centres(recs, db_path=db)
    rows=find_directory_centres(state='Telangana', db_path=db)
    assert len(rows)==1
    assert rows[0]['verification_status']=='OFFICIAL_DIRECTORY'
    # Directory batch count must never create a live offering.
    st=training_data_status(db)
    assert st['verified_directory_centres']==1
    assert st['offerings']==0
    assert st['open_or_active_offerings']==0
    assert directory_status(db)['verified_directory_centres']==1
