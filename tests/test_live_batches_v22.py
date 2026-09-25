import json
import sqlite3
from pathlib import Path

from backend.database.models import init_db_schema
from backend.training.live_batches import (
    ensure_live_batch_schema,
    import_live_batch_json,
    live_batch_status,
    find_live_batches,
)


def _db(tmp_path):
    p = tmp_path / "x.db"
    conn = sqlite3.connect(p)
    init_db_schema(conn)
    conn.close()
    ensure_live_batch_schema(p)
    return p


def test_import_and_search_active_batch(tmp_path):
    db = _db(tmp_path)
    payload = {
        "Data": {"Batches": [{
            "BatchId": "B-100",
            "TrainingCentreId": "TC-1",
            "TrainingCentre": "PMKK Hyderabad",
            "TrainingPartner": "Example TP",
            "QPCode": "SGJ/Q0101",
            "JobRole": "Solar PV Installer",
            "State": "Telangana",
            "District": "Hyderabad",
            "BatchStatus": "Active",
            "StartDate": "2026-09-20",
            "Capacity": 30,
            "SeatsAvailable": 7,
        }]}
    }
    f = tmp_path / "b.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    out = import_live_batch_json(f, db_path=db)
    assert out["records_imported"] == 1
    assert out["active_batches"] == 1
    rows = find_live_batches(qualification_code="SGJ/Q0101", state="Telangana", district="Hyderabad", db_path=db)
    assert len(rows) == 1
    assert rows[0]["seats_available"] == 7
    assert rows[0]["normalized_status"] == "VERIFIED_ACTIVE_BATCH"


def test_unknown_status_never_becomes_active(tmp_path):
    db = _db(tmp_path)
    payload = {"items": [{
        "BatchId": "B-200",
        "TrainingCentre": "Centre X",
        "JobRole": "Electrician",
        "State": "Telangana",
        "District": "Hyderabad"
    }]}
    f = tmp_path / "b.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    out = import_live_batch_json(f, db_path=db)
    assert out["status_unknown"] == 1
    assert find_live_batches(job_role="Electrician", active_only=True, db_path=db) == []
    rows = find_live_batches(job_role="Electrician", active_only=False, db_path=db)
    assert rows[0]["normalized_status"] == "VERIFIED_BATCH_STATUS_UNKNOWN"


def test_closed_batch_not_active(tmp_path):
    db = _db(tmp_path)
    payload = {"results": [{
        "BatchID": "B-300",
        "CenterName": "Centre Y",
        "CourseName": "Sewing Machine Operator",
        "StateName": "Telangana",
        "DistrictName": "Rangareddy",
        "Status": "Completed",
        "AvailableSeats": 0,
    }]}
    f = tmp_path / "b.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    import_live_batch_json(f, db_path=db)
    status = live_batch_status(db)
    assert status["verified_no_active_batches"] == 1
    assert status["seat_counts_known"] == 1


def test_unrelated_nested_objects_are_ignored(tmp_path):
    db = _db(tmp_path)
    payload = {"Data": {"Pagination": {"CurrentPageNumber": 1}, "User": {"State": "Telangana"}}}
    f = tmp_path / "b.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    out = import_live_batch_json(f, db_path=db)
    assert out["records_detected"] == 0


def test_real_sidh_scheme_batch_details_shape_is_active(tmp_path):
    db = _db(tmp_path)
    payload = {
        "IsSuccess": True,
        "StatusCode": 200,
        "Data": {
            "SchemeBatchDetails": [{
                "Address": "GASTC c/o 606 EME Bn Bareilly Cantt UP, PIN-243001",
                "BatchEndDate": "2027-02-10",
                "BatchId": 548792,
                "BatchStartDate": "2026-10-05",
                "BatchTiming": [{
                    "DayOfWeek": "Mon-Sat",
                    "EndTime": "2026-09-22T07:30:00Z",
                    "StartTime": "2026-09-22T03:30:00Z"
                }],
                "BatchType": "Regular",
                "CourseCode": "HSS/Q4003",
                "Status": None,
                "TcName": "GASTC BAREILLY",
                "TpName": "Directorate of Indian Army Veterans DIAV",
                "SipBatchId": "3955249",
                "BatchSize": 20,
                "SchemeName": "Short Term Training",
                "StateName": "UTTAR PRADESH",
                "DistrictName": "BAREILLY",
                "TcId": "TC012689"
            }],
            "Pagination": {"TotalCount": 1, "CurrentPageNumber": 1, "CurrentPageSize": 1}
        }
    }
    f = tmp_path / "sidh.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    out = import_live_batch_json(f, db_path=db)
    assert out["records_imported"] == 1
    assert out["active_batches"] == 1
    assert out["sidh_scheme_batch_details_detected"] == 1
    rows = find_live_batches(qualification_code="HSS/Q4003", state="UTTAR PRADESH", district="BAREILLY", db_path=db)
    assert len(rows) == 1
    r = rows[0]
    assert r["batch_id"] == "3955249"
    assert r["centre_id"] == "TC012689"
    assert r["centre_name"] == "GASTC BAREILLY"
    assert r["training_partner"] == "Directorate of Indian Army Veterans DIAV"
    assert r["capacity"] == 20
    assert r["seats_available"] is None
    assert r["normalized_status"] == "VERIFIED_ACTIVE_BATCH"
    assert "9:00 AM" in r["timing"] and "1:00 PM" in r["timing"]


def test_empty_sidh_scheme_batch_details_is_verified_empty_response(tmp_path):
    db = _db(tmp_path)
    payload = {
        "IsSuccess": True,
        "StatusCode": 200,
        "Data": {
            "SchemeBatchDetails": [],
            "Pagination": {"TotalCount": 0, "CurrentPageNumber": 1, "CurrentPageSize": 0}
        }
    }
    f = tmp_path / "empty.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    out = import_live_batch_json(f, db_path=db)
    assert out["records_imported"] == 0
    assert out["sidh_scheme_batch_details_detected"] == 0
    assert out["verified_empty_live_response"] is True
