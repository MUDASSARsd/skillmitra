from pathlib import Path
import importlib.util
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nqr_eligibility_harvester.py"
spec = importlib.util.spec_from_file_location("harvester", MODULE_PATH)
h = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = h
spec.loader.exec_module(h)


def test_extracts_multiple_official_routes():
    html = '''
    <html><body><h3>Eligibility Criteria</h3>
      <div>Qualification Code: 2024/SSC/TEST/1234</div>
      <table>
        <tr><th>Criteria 1</th><th>Criteria 2</th><th>Experience</th><th>Training Qualification</th></tr>
        <tr><td>12th</td><td>Completed</td><td>No Experience</td><td>None</td></tr>
        <tr><td>10th</td><td>Passed</td><td>2 years</td><td>ITI</td></tr>
      </table>
    </body></html>'''
    soup = h.BeautifulSoup(html, "html.parser")
    catalogue = {h.norm_code("2024/SSC/TEST/1234"): "2024/SSC/TEST/1234"}
    assert h.extract_page_codes(soup, catalogue) == ["2024/SSC/TEST/1234"]
    routes = h.extract_routes(soup, 999, "2024/SSC/TEST/1234", "https://www.nqr.gov.in/qualifications/999")
    assert len(routes) == 2
    assert routes[0].criteria_1 == "12th"
    assert routes[1].experience == "2 years"
    assert routes[1].training_qualification == "ITI"
    assert routes[0].verification_status == "VERIFIED_NQR_HTML"


def test_header_order_can_change():
    html = '''<table>
      <tr><th>Experience</th><th>Training Qualification</th><th>Criteria 2</th><th>Criteria 1</th></tr>
      <tr><td>1.5 Years</td><td>None</td><td>of Level 3.5</td><td>Previous NSQF qualification</td></tr>
    </table>'''
    soup = h.BeautifulSoup(html, "html.parser")
    routes = h.extract_routes(soup, 1, "X", "u")
    assert routes[0].criteria_1 == "Previous NSQF qualification"
    assert routes[0].criteria_2 == "of Level 3.5"
    assert routes[0].experience == "1.5 Years"


def test_merge_routes_is_idempotent():
    row = {"nqr_id": 1, "code": "A", "route": 1, "criteria_1": "10th"}
    merged = h.merge_routes([row], [row])
    assert len(merged) == 1


def test_extract_qualification_ids_from_html_mixed_links():
    from scripts.nqr_eligibility_harvester import extract_qualification_ids_from_html
    html = '''
    <a href="/qualifications/1284">A</a>
    <script>const x="https://www.nqr.gov.in/qualifications/3063?foo=1";</script>
    <a href="/qualifications-search/7">not a qualification</a>
    <a href="/qualifications/1284">duplicate</a>
    '''
    assert extract_qualification_ids_from_html(html) == {1284, 3063}


def test_extracts_current_dash_format_code():
    html = '''<html><body>
      <div>NQR Code: NG-2.5-AG-00738-2023-V1-ASCI</div>
      <h3>Eligibility Criteria</h3>
      <table>
        <tr><th>Criteria 1</th><th>Criteria 2</th><th>Experience</th><th>Training Qualification</th></tr>
        <tr><td>None</td><td>None</td><td>No Experience</td><td>None</td></tr>
      </table>
    </body></html>'''
    soup = h.BeautifulSoup(html, "html.parser")
    code = "NG-2.5-AG-00738-2023-V1-ASCI"
    catalogue = {h.canonical_code(code): code}
    assert h.extract_page_codes(soup, catalogue) == [code]


def test_dirty_local_code_canonicalizes_to_official_code():
    dirty = "Code: QG-04-PD-03680-2025-V1-SCPWD"
    clean = "QG-04-PD-03680-2025-V1-SCPWD"
    assert h.canonical_code(dirty) == clean
    assert h.canonical_code(clean) == clean


def test_compact_ncvET_code_is_repaired():
    dirty = "NCVET-NG-02-CO-046382025-V1-ICES"
    assert h.canonical_code(dirty) == "NG-02-CO-04638-2025-V1-ICES"


def test_nqr_code_label_does_not_break_matching():
    html = '<div>NQR CODE- QG-04-FI-04210-2025-V1-FICSI</div>'
    soup = h.BeautifulSoup(html, "html.parser")
    code = "NQR CODE- QG-04-FI-04210-2025-V1-FICSI"
    catalogue = {h.canonical_code(code): code}
    assert h.extract_page_codes(soup, catalogue) == [code]
