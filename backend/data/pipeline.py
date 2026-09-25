"""
Data Pipeline Orchestrator.
Initializes SQLite database, runs dataset loaders, and generates a comprehensive Data Quality Report.
"""
import json
from pathlib import Path
from backend.database.db import get_db_connection, init_db
from backend.data.nqr_loader import load_nqr_qualifications
from backend.data.eligibility_loader import load_eligibility_routes

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCEL_PATH = BASE_DIR / "Qualifications.xlsx"
DEFAULT_ROUTES_CSV_PATH = BASE_DIR / "eligibility_routes.csv"
DEFAULT_REPORT_PATH = BASE_DIR / "data" / "data_quality_report.json"


def run_data_pipeline(excel_path=None, routes_path=None, db_path=None, report_path=None):
    """
    Executes Phase 1 data pipeline:
    1. Initializes SQLite DB & schemas
    2. Imports Qualifications.xlsx
    3. Imports eligibility_routes.csv
    4. Generates data quality report
    """
    excel_p = Path(excel_path) if excel_path else DEFAULT_EXCEL_PATH
    routes_p = Path(routes_path) if routes_path else DEFAULT_ROUTES_CSV_PATH
    report_p = Path(report_path) if report_path else DEFAULT_REPORT_PATH
    
    conn = init_db(db_path)
    
    print(f"Loading NQR Qualifications from: {excel_p}")
    nqr_metrics = load_nqr_qualifications(excel_p, conn)
    
    print(f"Loading Eligibility Routes from: {routes_p}")
    eligibility_metrics = load_eligibility_routes(routes_p, conn)
    
    report = {
        "status": "SUCCESS",
        "nqr_metrics": nqr_metrics,
        "eligibility_metrics": eligibility_metrics,
        "overall_summary": {
            "total_qualification_records": nqr_metrics["total_qualification_records"],
            "unique_qualification_codes": nqr_metrics["unique_qualification_codes"],
            "duplicate_codes_list": nqr_metrics["duplicate_code_values"],
            "null_code_records_count": nqr_metrics["null_code_records_count"],
            "eligibility_route_count": eligibility_metrics["total_eligibility_routes_imported"],
            "qualifications_with_eligibility_data": eligibility_metrics["qualifications_with_eligibility_data"],
            "qualifications_without_eligibility_data": eligibility_metrics["qualifications_without_eligibility_data"],
            "eligibility_coverage_percentage": eligibility_metrics["eligibility_coverage_percentage"]
        }
    }
    
    report_p.parent.mkdir(parents=True, exist_ok=True)
    with open(report_p, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
        
    print(f"\nPipeline completed successfully! Report saved to: {report_p}")
    return report


if __name__ == "__main__":
    run_data_pipeline()
