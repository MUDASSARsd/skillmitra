import csv
from pathlib import Path

from backend.database.db import init_db
from backend.training.store import import_training_csv, find_training_options, training_data_status


def test_training_import_and_location_filter(tmp_path):
    db = tmp_path / "test.db"
    init_db(db).close()
    src = tmp_path / "centres.csv"
    fields = [
        "centre_id","centre_name","training_partner","state","district","address","pincode","latitude","longitude",
        "qualification_code","job_role","sector","scheme","batch_id","delivery_mode","batch_start_date","batch_end_date",
        "batch_timing","availability_status","source","source_url","verification_status","last_verified_at"
    ]
    with src.open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader()
        w.writerow({
            "centre_id":"TC1","centre_name":"Test Hyderabad Centre","training_partner":"Partner A","state":"Telangana",
            "district":"Hyderabad","qualification_code":"QG-TEST-1","job_role":"Solar Technician","scheme":"PMKVY 4.0",
            "batch_id":"B1","availability_status":"OPEN","source":"official_test","verification_status":"OFFICIAL_SOURCE",
            "last_verified_at":"2026-09-24T00:00:00+00:00"
        })
        w.writerow({
            "centre_id":"TC2","centre_name":"Other District Centre","state":"Telangana","district":"Warangal",
            "qualification_code":"QG-TEST-1","job_role":"Solar Technician","availability_status":"UNKNOWN",
            "source":"official_test","verification_status":"OFFICIAL_SOURCE","last_verified_at":"2026-09-24T00:00:00+00:00"
        })
    result=import_training_csv(src, db)
    assert result["offerings_upserted"] == 2
    opts=find_training_options(qualification_code="QG-TEST-1", state="Telangana", district="Hyderabad", db_path=db)
    assert len(opts)==1
    assert opts[0].centre.centre_name == "Test Hyderabad Centre"
    assert opts[0].location_match == "DISTRICT"
    st=training_data_status(db)
    assert st["training_centres"] == 2
    assert st["offerings"] == 2
    assert st["open_or_active_offerings"] == 1


def test_training_import_is_idempotent(tmp_path):
    db=tmp_path / "test.db"; init_db(db).close()
    src=tmp_path / "c.csv"
    src.write_text("centre_id,centre_name,state,district,qualification_code,job_role,batch_id,availability_status,source,verification_status,last_verified_at\nTC1,Centre,Telangana,Hyderabad,Q1,Role,B1,OPEN,official,OFFICIAL_SOURCE,2026-09-24T00:00:00+00:00\n", encoding="utf-8")
    import_training_csv(src,db); import_training_csv(src,db)
    st=training_data_status(db)
    assert st["training_centres"]==1 and st["offerings"]==1
