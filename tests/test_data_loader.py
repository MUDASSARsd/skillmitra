"""
Unit Tests for Phase 1: NQR & Eligibility Data Pipeline using standard unittest framework.
"""
import unittest
import tempfile
import sqlite3
from pathlib import Path
import pytest
pytest.importorskip("pandas")

from backend.database.db import init_db
from backend.data.nqr_loader import load_nqr_qualifications, parse_numeric_level
from backend.data.eligibility_loader import load_eligibility_routes, parse_experience_months
from backend.data.pipeline import run_data_pipeline

BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_PATH = BASE_DIR / "Qualifications.xlsx"
ROUTES_CSV_PATH = BASE_DIR / "eligibility_routes.csv"


class TestDataPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        self.conn = init_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        try:
            Path(self.db_path).unlink()
        except OSError:
            pass

    def test_experience_months_parsing(self):
        self.assertEqual(parse_experience_months("1 year"), 12)
        self.assertEqual(parse_experience_months("4 years"), 48)
        self.assertEqual(parse_experience_months("1.5 Years"), 18)
        self.assertEqual(parse_experience_months("6 months"), 6)
        self.assertEqual(parse_experience_months("No Experience"), 0)
        self.assertEqual(parse_experience_months(None), 0)

    def test_numeric_level_parsing(self):
        self.assertEqual(parse_numeric_level("Level 3"), 3.0)
        self.assertEqual(parse_numeric_level("Level 4.5"), 4.5)
        self.assertEqual(parse_numeric_level("Level 7"), 7.0)
        self.assertIsNone(parse_numeric_level(None))

    def test_pipeline_import(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            report_path = f.name

        report = run_data_pipeline(
            excel_path=EXCEL_PATH,
            routes_path=ROUTES_CSV_PATH,
            db_path=self.db_path,
            report_path=report_path
        )

        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["overall_summary"]["total_qualification_records"], 2814)
        # Eligibility coverage grows as the official NQR harvester enriches the
        # project. Validate against the current harvested CSV rather than the
        # original Phase-1 fixture count (11).
        import csv
        with ROUTES_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as routes_file:
            expected_route_count = sum(1 for _ in csv.DictReader(routes_file))
        self.assertEqual(report["overall_summary"]["eligibility_route_count"], expected_route_count)
        self.assertIn("QG-04-ES-00913-2023-V1-SCGJ", report["overall_summary"]["duplicate_codes_list"])

    def test_duplicate_code_flagging(self):
        load_nqr_qualifications(EXCEL_PATH, self.conn)
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, s_no, title, is_duplicate_code FROM qualifications WHERE code = 'QG-04-ES-00913-2023-V1-SCGJ'")
        rows = cursor.fetchall()
        
        self.assertEqual(len(rows), 2, "Duplicate code should exist for 2 records")
        for r in rows:
            self.assertEqual(r["is_duplicate_code"], 1, "Duplicate code flag should be set to 1")

    def test_null_code_handling(self):
        load_nqr_qualifications(EXCEL_PATH, self.conn)
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, s_no, title, code FROM qualifications WHERE s_no = 1993")
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "Environment Sustainability Governance (ESG) Specialist")
        self.assertIsNone(row["code"])

    def test_fts5_search_indexing(self):
        load_nqr_qualifications(EXCEL_PATH, self.conn)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT q.title, q.code, q.sector_name
            FROM qualifications_fts fts
            JOIN qualifications q ON fts.qualification_id = q.id
            WHERE qualifications_fts MATCH 'Hydrocarbon'
            LIMIT 10;
        """)
        results = cursor.fetchall()
        
        self.assertGreaterThan(len(results), 0) if hasattr(self, 'assertGreaterThan') else self.assertTrue(len(results) > 0)

    def test_eligibility_route_linking(self):
        load_nqr_qualifications(EXCEL_PATH, self.conn)
        load_eligibility_routes(ROUTES_CSV_PATH, self.conn)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT q.title, e.route_number, e.criteria_1, e.experience_months
            FROM qualifications q
            JOIN eligibility_routes e ON q.code = e.code
            WHERE q.code = '2020/HYC/HSSCI/3770'
            ORDER BY e.route_number;
        """)
        routes = cursor.fetchall()
        
        self.assertEqual(len(routes), 4, "Line Patrolling Man should have 4 eligibility routes")
        self.assertEqual(routes[0]["criteria_1"], "8th")
        self.assertEqual(routes[0]["experience_months"], 12)


if __name__ == "__main__":
    unittest.main()
