"""Official NQR eligibility harvester for SkillMitra.

Goals
-----
* Never invent eligibility rules.
* Keep every NQR table row as an alternative (OR) route.
* Preserve source URL/raw text for auditability.
* Resume safely after interruptions.
* Match pages to the local catalogue by official qualification code.

Examples
--------
Fast harvest of IDs already present in qualification_mapping.csv:
    python scripts/nqr_eligibility_harvester.py harvest-known

Discover mappings/eligibility in an ID range (resumable):
    python scripts/nqr_eligibility_harvester.py discover --start-id 1 --end-id 16000

Small trial first:
    python scripts/nqr_eligibility_harvester.py discover --start-id 1200 --end-id 1350

After harvesting, import CSV into SQLite:
    python scripts/import_eligibility.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "nqr_database.db"
MAPPING_CSV = ROOT / "qualification_mapping.csv"
ROUTES_CSV = ROOT / "eligibility_routes.csv"
CHECKPOINT_PATH = ROOT / "data" / "eligibility_harvest_checkpoint.json"
COVERAGE_REPORT = ROOT / "data" / "eligibility_coverage_report.json"
BASE_URL = "https://www.nqr.gov.in/qualifications/{}"
SITE_ROOT = "https://www.nqr.gov.in"
CATALOGUE_URLS = [
    f"{SITE_ROOT}/qualifications-search",
    f"{SITE_ROOT}/filter-search",
]
CATALOGUE_CHECKPOINT_PATH = ROOT / "data" / "eligibility_catalogue_checkpoint.json"
DISCOVERED_IDS_PATH = ROOT / "data" / "nqr_discovered_ids.json"
QUALIFICATION_URL_RE = re.compile(r"(?:https?://(?:www\.)?nqr\.gov\.in)?/qualifications/(\d+)(?:[/?#\"\'\s<]|$)", re.I)

EXPECTED_HEADERS = {
    "criteria 1": "criteria_1",
    "criteria 2": "criteria_2",
    "experience": "experience",
    "training qualification": "training_qualification",
}

# NQR has used multiple qualification-code generations. Older pages often use
# year/sector/body/number codes (for example 2022/HLT/HSSC/06763), while most
# newer qualifications use codes such as NG-2.5-AG-00738-2023-V1-ASCI or
# QG-04-IT-02637-2024-V1-ITDA.  A few imported catalogue cells also contain
# labels/punctuation around the real code, so extraction and canonicalization
# must work on arbitrary surrounding text rather than assuming the whole cell is
# already clean.
OLD_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])((?:19|20)\d{2}/[A-Za-z0-9&._()\-]+/[A-Za-z0-9&._()\-]+/[A-Za-z0-9&._()\-]+)",
    re.I,
)
NEW_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])((?:NCVET-)?(?:NG|QG|NM|NC|G|QC|QM)-\d+(?:\.\d+)?-[A-Z]{2,6}-\d{4,9}-\d{4}-V\d+(?:\.\d+)?-[A-Z0-9]{2,12})(?![A-Za-z0-9])",
    re.I,
)
OTHER_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(ICE/CONS/\d{2}/Q\d+)(?![A-Za-z0-9])", re.I)
COMPACT_NEW_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])((?:NCVET-)?(?:NG|QG|NM|NC|G|QC|QM)-\d+(?:\.\d+)?-[A-Z]{2,6}-\d{5}20\d{2}-V\d+(?:\.\d+)?-[A-Z0-9]{2,12})(?![A-Za-z0-9])",
    re.I,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def norm_code(value: str | None) -> str:
    """Legacy normalizer kept for compatibility with existing tests/callers."""
    s = clean(value).upper()
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s)


def _repair_compact_new_code(code: str) -> str:
    """Repair rare cells where the 5-digit sequence and year were concatenated.

    Example: NCVET-NG-02-CO-046382025-V1-ICES -> NG-02-CO-04638-2025-V1-ICES
    """
    code = re.sub(r"^NCVET-", "", code, flags=re.I)
    m = re.fullmatch(
        r"((?:NG|QG|NM|NC|G|QC|QM)-\d+(?:\.\d+)?-[A-Z]{2,6}-)(\d{5})(20\d{2})(-V\d+(?:\.\d+)?-[A-Z0-9]{2,12})",
        code, flags=re.I,
    )
    if m:
        return f"{m.group(1)}{m.group(2)}-{m.group(3)}{m.group(4)}"
    return code


def _normalize_codeish_text(value: str | None) -> str:
    text = clean(value).upper().replace("–", "-").replace("—", "-").replace("\u00a0", " ")
    # Normalize spacing around separators seen in manually curated catalogue cells.
    text = re.sub(r"\s*-\s*", "-", text)
    # Missing separator between level and sector: QG-6.5IT-... -> QG-6.5-IT-...
    text = re.sub(
        r"\b((?:NG|QG|NM|NC|G|QC|QM)-\d+(?:\.\d+)?)([A-Z]{2,6})-",
        r"\1-\2-", text, flags=re.I,
    )
    # Missing separator between sector and serial: QG-03-HY00597-... -> ...-HY-00597-...
    text = re.sub(
        r"\b((?:NG|QG|NM|NC|G|QC|QM)-\d+(?:\.\d+)?-[A-Z]{2,6})(\d{4,5})(?=-)",
        r"\1-\2", text, flags=re.I,
    )
    # A few exports separate version/body with a space rather than a dash.
    text = re.sub(r"(V\d+(?:\.\d+)?)\s+([A-Z][A-Z0-9]{1,11})\b", r"\1-\2", text)
    # Sequence and year occasionally arrive concatenated: 046072025 -> 04607-2025.
    text = re.sub(
        r"(-[A-Z]{2,6}-)(\d{4,5})(20\d{2})(?=-V)",
        r"\1\2-\3", text, flags=re.I,
    )
    return text


def extract_code_candidates(value: str | None) -> list[str]:
    """Extract and repair official qualification codes from arbitrary text."""
    text = _normalize_codeish_text(value)
    if not text:
        return []
    hits: list[str] = []

    for regex in (OLD_CODE_RE, NEW_CODE_RE, COMPACT_NEW_CODE_RE, OTHER_CODE_RE):
        for match in regex.finditer(text):
            code = _repair_compact_new_code(match.group(1).strip(" .,:;•\t"))
            if code not in hits:
                hits.append(code)

    # Flexible current-code family. Allows QC/QM, optional year/body, and 4-5
    # digit sequence numbers found in a small number of current NQR exports.
    flex = re.compile(
        r"(?<![A-Za-z0-9])((?:NG|QG|NM|NC|G|QC|QM)-\d+(?:\.\d+)?-[A-Z]{2,6}-\d{4,5}(?:-20\d{2})?(?:-V\d+(?:\.\d+)?)?(?:-[A-Z0-9]{2,12})?)(?![A-Za-z0-9])",
        re.I,
    )
    for match in flex.finditer(text):
        code = _repair_compact_new_code(match.group(1).strip(" .,:;•\t"))
        if code not in hits:
            hits.append(code)

    return hits


def canonical_code(value: str | None) -> str:
    """Return a stable comparison key for any known NQR code generation.

    Surrounding labels such as "NQR Code-" and "Code:" are intentionally
    ignored.  The original database value is still preserved in output files.
    """
    candidates = extract_code_candidates(value)
    if candidates:
        return re.sub(r"\s+", "", candidates[0].upper())
    # Fall back to the old behavior for unknown/custom code families.
    return norm_code(value).strip(" .,:;•")


def session_with_retries() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8))
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36 "
            "SkillMitra-NQR-Eligibility-Research/1.0"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
    })
    return s




def extract_qualification_ids_from_html(html: str) -> set[int]:
    """Extract real NQR qualification IDs from links or embedded page data."""
    ids: set[int] = set()
    for match in QUALIFICATION_URL_RE.finditer(html or ""):
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if value > 0:
            ids.add(value)
    return ids


def discover_ids_from_sitemaps(session: requests.Session, timeout: float) -> set[int]:
    """Best-effort sitemap discovery. Returns empty set when NQR exposes no sitemap."""
    pending = [
        f"{SITE_ROOT}/sitemap.xml",
        f"{SITE_ROOT}/sitemap_index.xml",
        f"{SITE_ROOT}/sitemap-index.xml",
    ]
    seen: set[str] = set()
    ids: set[int] = set()
    while pending and len(seen) < 40:
        url = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code != 200:
                continue
            text = r.text
            ids.update(extract_qualification_ids_from_html(text))
            # sitemap indexes may point to child sitemap XML files
            for child in re.findall(r"<loc>\s*(https?://[^<]+\.xml(?:\?[^<]*)?)\s*</loc>", text, flags=re.I):
                if "nqr.gov.in" in child.lower() and child not in seen:
                    pending.append(child.strip())
        except requests.RequestException:
            continue
    return ids


def discover_ids_from_catalogue_pages(session: requests.Session, timeout: float, max_sector_id: int = 80) -> set[int]:
    """Discover qualification links from NQR catalogue/filter/sector pages.

    NQR has historically changed its search UI. We therefore parse both normal
    anchors and URLs embedded in scripts/JSON instead of depending on CSS.
    """
    ids: set[int] = set()
    urls = list(CATALOGUE_URLS)
    urls.extend(f"{SITE_ROOT}/qualifications-search/{i}" for i in range(1, max_sector_id + 1))
    for idx, url in enumerate(urls, 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                found = extract_qualification_ids_from_html(r.text)
                before = len(ids)
                ids.update(found)
                if found:
                    print(f"Catalogue [{idx}/{len(urls)}] +{len(ids)-before} IDs ({len(ids)} unique): {url}")
        except requests.RequestException as exc:
            print(f"Catalogue request failed: {url} ({type(exc).__name__})")
    return ids


def save_discovered_ids(ids: set[int], sources: list[str]) -> None:
    DISCOVERED_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_iso(),
        "count": len(ids),
        "sources": sources,
        "ids": sorted(ids),
    }
    DISCOVERED_IDS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_discovered_ids() -> set[int]:
    try:
        payload = json.loads(DISCOVERED_IDS_PATH.read_text(encoding="utf-8"))
        return {int(x) for x in payload.get("ids", []) if int(x) > 0}
    except Exception:
        return set()


def load_catalogue_codes(db_path: Path) -> tuple[dict[str, str], dict[str, dict]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT code, title, sector_name, level FROM qualifications WHERE code IS NOT NULL AND TRIM(code) <> ''"
    ).fetchall()
    con.close()
    normalized: dict[str, str] = {}
    meta: dict[str, dict] = {}
    for row in rows:
        original = clean(row["code"])
        key = canonical_code(original)
        if key:
            normalized.setdefault(key, original)
            meta.setdefault(original, dict(row))
    return normalized, meta


def table_headers(table) -> list[str]:
    # Some NQR pages use td in the first row rather than th.
    first = table.find("tr")
    if not first:
        return []
    return [clean(c.get_text(" ", strip=True)).lower() for c in first.find_all(["th", "td"])]


def find_eligibility_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        headers = table_headers(table)
        if all(h in headers for h in EXPECTED_HEADERS):
            return table, headers
    return None, []


def extract_page_codes(soup: BeautifulSoup, catalogue: dict[str, str]) -> list[str]:
    """Return local catalogue codes found on an NQR page.

    V15.2 only recognized the legacy year/slash code family.  Most current NQR
    records use NG/QG/NM/NC dash codes, which caused the 11.7% coverage plateau.
    This version extracts every supported code family from both visible text and
    raw HTML, then validates candidates against the local catalogue.
    """
    visible = clean(soup.get_text(" ", strip=True))
    raw = str(soup)
    hits: list[str] = []
    for candidate in [*extract_code_candidates(visible), *extract_code_candidates(raw)]:
        key = canonical_code(candidate)
        if key in catalogue and catalogue[key] not in hits:
            hits.append(catalogue[key])

    if hits:
        return hits

    # Last-resort exact canonical-code search. This helps when a page breaks a
    # displayed code across nested spans and regex extraction cannot see it as a
    # contiguous token. Only do this for codes whose distinctive token occurs in
    # the page to avoid O(N) substring checks on every request.
    compact_page = re.sub(r"\s+", "", (visible + " " + raw).upper())
    for key, original in catalogue.items():
        if len(key) >= 12 and key in compact_page and original not in hits:
            hits.append(original)
    return hits


@dataclass(frozen=True)
class EligibilityRouteRow:
    nqr_id: int
    code: str
    route: int
    criteria_1: str
    criteria_2: str
    experience: str
    training_qualification: str
    source_url: str
    verification_status: str
    fetched_at: str
    raw_text: str


def extract_routes(soup: BeautifulSoup, nqr_id: int, code: str, url: str) -> list[EligibilityRouteRow]:
    table, headers = find_eligibility_table(soup)
    if table is None:
        return []

    positions = {name: headers.index(name) for name in EXPECTED_HEADERS}
    rows: list[EligibilityRouteRow] = []
    trs = table.find_all("tr")[1:]
    route_number = 1
    for tr in trs:
        cells = [clean(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
        if not cells or all(not x for x in cells):
            continue
        max_pos = max(positions.values())
        if len(cells) <= max_pos:
            continue
        c1 = cells[positions["criteria 1"]]
        c2 = cells[positions["criteria 2"]]
        exp = cells[positions["experience"]]
        tq = cells[positions["training qualification"]]
        if not any((c1, c2, exp, tq)):
            continue
        raw = " | ".join((c1, c2, exp, tq))
        rows.append(EligibilityRouteRow(
            nqr_id=nqr_id,
            code=code,
            route=route_number,
            criteria_1=c1,
            criteria_2=c2,
            experience=exp,
            training_qualification=tq,
            source_url=url,
            verification_status="VERIFIED_NQR_HTML",
            fetched_at=now_iso(),
            raw_text=raw,
        ))
        route_number += 1
    return rows


def fetch_page(session: requests.Session, nqr_id: int, timeout: float) -> tuple[str, BeautifulSoup] | None:
    url = BASE_URL.format(nqr_id)
    response = session.get(url, timeout=timeout)
    if response.status_code != 200:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    text = clean(soup.get_text(" ", strip=True)).lower()
    # Guard against generic error/redirect pages that still return HTTP 200.
    if "eligibility criteria" not in text and "about this qualification" not in text:
        return None
    return url, soup


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def atomic_write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def merge_mapping(existing: list[dict], additions: Iterable[dict]) -> list[dict]:
    by_key: dict[tuple[int, str], dict] = {}
    for row in [*existing, *additions]:
        try:
            nqr_id = int(row.get("nqr_id", 0))
        except (TypeError, ValueError):
            continue
        code = clean(row.get("code"))
        if nqr_id and code:
            row = dict(row)
            row["nqr_id"] = nqr_id
            by_key[(nqr_id, code)] = row
    return sorted(by_key.values(), key=lambda x: (int(x["nqr_id"]), x["code"]))


def merge_routes(existing: list[dict], additions: Iterable[dict]) -> list[dict]:
    by_key: dict[tuple[int, str, int], dict] = {}
    for row in [*existing, *additions]:
        try:
            key = (int(row.get("nqr_id", 0)), clean(row.get("code")), int(row.get("route", 0)))
        except (TypeError, ValueError):
            continue
        if key[0] and key[1] and key[2]:
            normalized = dict(row)
            normalized.update({"nqr_id": key[0], "code": key[1], "route": key[2]})
            by_key[key] = normalized
    return sorted(by_key.values(), key=lambda x: (int(x["nqr_id"]), x["code"], int(x["route"])))


def save_outputs(mapping_rows: list[dict], route_rows: list[dict]) -> None:
    mapping_fields = ["nqr_id", "code", "title", "sector", "nsqf_level", "url"]
    route_fields = [
        "nqr_id", "code", "route", "criteria_1", "criteria_2", "experience",
        "training_qualification", "source_url", "verification_status", "fetched_at", "raw_text"
    ]
    atomic_write_csv(MAPPING_CSV, mapping_rows, mapping_fields)
    atomic_write_csv(ROUTES_CSV, route_rows, route_fields)


def write_checkpoint(last_id: int, stats: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps({"last_id": last_id, "updated_at": now_iso(), **stats}, indent=2), encoding="utf-8")


def load_checkpoint() -> dict:
    try:
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def coverage_report(db_path: Path, route_rows: list[dict], mapping_rows: list[dict]) -> dict:
    con = sqlite3.connect(db_path)
    total_codes = con.execute("SELECT COUNT(DISTINCT code) FROM qualifications WHERE code IS NOT NULL AND TRIM(code) <> ''").fetchone()[0]
    con.close()
    covered_codes = {clean(r.get("code")) for r in route_rows if clean(r.get("code"))}
    mapped_codes = {clean(r.get("code")) for r in mapping_rows if clean(r.get("code"))}
    report = {
        "generated_at": now_iso(),
        "unique_qualification_codes": total_codes,
        "mapped_to_nqr_id": len(mapped_codes),
        "qualifications_with_eligibility": len(covered_codes),
        "eligibility_routes": len(route_rows),
        "mapping_coverage_percentage": round(100 * len(mapped_codes) / total_codes, 2) if total_codes else 0,
        "eligibility_coverage_percentage": round(100 * len(covered_codes) / total_codes, 2) if total_codes else 0,
    }
    COVERAGE_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def make_mapping_row(nqr_id: int, code: str, meta: dict, url: str) -> dict:
    return {
        "nqr_id": nqr_id,
        "code": code,
        "title": clean(meta.get("title")),
        "sector": clean(meta.get("sector_name")),
        "nsqf_level": clean(meta.get("level")),
        "url": url,
    }


def harvest_known(args) -> int:
    catalogue, meta = load_catalogue_codes(Path(args.db))
    existing_mapping = read_csv(Path(args.mapping))
    existing_routes = read_csv(Path(args.routes))
    known: dict[int, list[str]] = {}
    for r in existing_mapping:
        try:
            nqr_id = int(r.get("nqr_id", 0))
        except ValueError:
            continue
        code = clean(r.get("code"))
        if nqr_id and code:
            known.setdefault(nqr_id, []).append(code)

    if not known:
        print("No known NQR IDs in mapping CSV. Use discover mode first.")
        return 2

    session = session_with_retries()
    additions: list[dict] = []
    for index, (nqr_id, codes) in enumerate(sorted(known.items()), 1):
        try:
            page = fetch_page(session, nqr_id, args.timeout)
            if page:
                url, soup = page
                page_codes = extract_page_codes(soup, catalogue)
                use_codes = [c for c in codes if c in page_codes] or codes
                for code in use_codes:
                    additions.extend(asdict(r) for r in extract_routes(soup, nqr_id, code, url))
            print(f"[{index}/{len(known)}] NQR {nqr_id}: {len(additions)} cumulative routes")
        except KeyboardInterrupt:
            print("Interrupted; saving partial results...")
            break
        except Exception as exc:
            print(f"NQR {nqr_id}: {type(exc).__name__}: {exc}")
        time.sleep(args.delay)

    merged_routes = merge_routes(existing_routes, additions)
    save_outputs(merge_mapping(existing_mapping, []), merged_routes)
    report = coverage_report(Path(args.db), merged_routes, existing_mapping)
    print(json.dumps(report, indent=2))
    return 0


def discover(args) -> int:
    db_path = Path(args.db)
    catalogue, meta = load_catalogue_codes(db_path)
    mapping_rows = read_csv(Path(args.mapping))
    route_rows = read_csv(Path(args.routes))
    already_mapped_ids = {int(r["nqr_id"]) for r in mapping_rows if str(r.get("nqr_id", "")).isdigit()}

    start_id = args.start_id
    if args.resume:
        cp = load_checkpoint()
        if cp.get("last_id") and int(cp["last_id"]) >= start_id:
            start_id = int(cp["last_id"]) + 1
            print(f"Resuming from NQR ID {start_id}")

    session = session_with_retries()
    stats = {"pages_checked": 0, "valid_pages": 0, "new_mappings": 0, "new_routes": 0, "errors": 0}
    pending_map: list[dict] = []
    pending_routes: list[dict] = []

    for nqr_id in range(start_id, args.end_id + 1):
        if args.skip_known and nqr_id in already_mapped_ids:
            write_checkpoint(nqr_id, stats)
            continue
        stats["pages_checked"] += 1
        try:
            page = fetch_page(session, nqr_id, args.timeout)
            if page:
                stats["valid_pages"] += 1
                url, soup = page
                codes = extract_page_codes(soup, catalogue)
                if codes:
                    for code in codes:
                        pending_map.append(make_mapping_row(nqr_id, code, meta.get(code, {}), url))
                        routes = extract_routes(soup, nqr_id, code, url)
                        pending_routes.extend(asdict(r) for r in routes)
                        stats["new_mappings"] += 1
                        stats["new_routes"] += len(routes)
                    print(f"MATCH NQR {nqr_id}: {', '.join(codes)} | +{len(pending_routes)} buffered routes")
        except KeyboardInterrupt:
            print("\nInterrupted; writing checkpoint and partial results...")
            break
        except requests.RequestException as exc:
            stats["errors"] += 1
            print(f"HTTP error NQR {nqr_id}: {type(exc).__name__}")
        except Exception as exc:
            stats["errors"] += 1
            print(f"Parse error NQR {nqr_id}: {type(exc).__name__}: {exc}")

        if stats["pages_checked"] % args.flush_every == 0:
            mapping_rows = merge_mapping(mapping_rows, pending_map)
            route_rows = merge_routes(route_rows, pending_routes)
            save_outputs(mapping_rows, route_rows)
            pending_map.clear(); pending_routes.clear()
            write_checkpoint(nqr_id, stats)
            report = coverage_report(db_path, route_rows, mapping_rows)
            print(
                f"Progress ID={nqr_id} | pages={stats['pages_checked']} | "
                f"mapped={report['mapped_to_nqr_id']}/{report['unique_qualification_codes']} | "
                f"eligibility={report['eligibility_coverage_percentage']}%"
            )
        time.sleep(args.delay)
    else:
        nqr_id = args.end_id

    mapping_rows = merge_mapping(mapping_rows, pending_map)
    route_rows = merge_routes(route_rows, pending_routes)
    save_outputs(mapping_rows, route_rows)
    write_checkpoint(nqr_id, stats)
    report = coverage_report(db_path, route_rows, mapping_rows)
    print("\nFinal coverage:")
    print(json.dumps(report, indent=2))
    return 0



def discover_catalogue(args) -> int:
    """Discover real qualification IDs first, then harvest only those pages."""
    db_path = Path(args.db)
    catalogue, meta = load_catalogue_codes(db_path)
    mapping_rows = read_csv(Path(args.mapping))
    route_rows = read_csv(Path(args.routes))
    already_mapped_ids = {int(r["nqr_id"]) for r in mapping_rows if str(r.get("nqr_id", "")).isdigit()}

    session = session_with_retries()
    discovered = set() if args.refresh_ids else load_discovered_ids()
    sources: list[str] = []

    if not discovered or args.refresh_ids:
        print("Discovering qualification links from official NQR catalogue/sitemaps...")
        sitemap_ids = discover_ids_from_sitemaps(session, args.timeout)
        if sitemap_ids:
            print(f"Sitemap discovery found {len(sitemap_ids)} qualification IDs")
            discovered.update(sitemap_ids)
            sources.append("sitemap")
        catalogue_ids = discover_ids_from_catalogue_pages(session, args.timeout, args.max_sector_id)
        if catalogue_ids:
            print(f"Catalogue discovery found {len(catalogue_ids)} qualification IDs")
            discovered.update(catalogue_ids)
            sources.append("catalogue")
        save_discovered_ids(discovered, sources)
    else:
        print(f"Using cached discovered ID list: {len(discovered)} IDs")

    if not discovered:
        print("No direct qualification links were exposed by the current NQR catalogue HTML.")
        print("Fallback: use the resumable 'discover' ID-range command, or rerun later if the site changes.")
        return 3

    ids = sorted(discovered)
    checkpoint = {}
    if args.resume:
        try:
            checkpoint = json.loads(CATALOGUE_CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            checkpoint = {}
    done_ids = {int(x) for x in checkpoint.get("done_ids", []) if str(x).isdigit()}

    stats = {"pages_checked": 0, "valid_pages": 0, "new_mappings": 0, "new_routes": 0, "errors": 0}
    pending_map: list[dict] = []
    pending_routes: list[dict] = []
    processed = 0

    for nqr_id in ids:
        if args.skip_known and nqr_id in already_mapped_ids:
            done_ids.add(nqr_id)
            continue
        if args.resume and nqr_id in done_ids:
            continue
        stats["pages_checked"] += 1
        try:
            page = fetch_page(session, nqr_id, args.timeout)
            if page:
                stats["valid_pages"] += 1
                url, soup = page
                codes = extract_page_codes(soup, catalogue)
                if codes:
                    for code in codes:
                        pending_map.append(make_mapping_row(nqr_id, code, meta.get(code, {}), url))
                        routes = extract_routes(soup, nqr_id, code, url)
                        pending_routes.extend(asdict(r) for r in routes)
                        stats["new_mappings"] += 1
                        stats["new_routes"] += len(routes)
                    print(f"MATCH NQR {nqr_id}: {', '.join(codes)} | {len(pending_routes)} buffered routes")
            done_ids.add(nqr_id)
        except KeyboardInterrupt:
            print("\nInterrupted; saving catalogue checkpoint and partial results...")
            break
        except requests.RequestException as exc:
            stats["errors"] += 1
            print(f"HTTP error NQR {nqr_id}: {type(exc).__name__}")
        except Exception as exc:
            stats["errors"] += 1
            print(f"Parse error NQR {nqr_id}: {type(exc).__name__}: {exc}")

        processed += 1
        if processed % args.flush_every == 0:
            mapping_rows = merge_mapping(mapping_rows, pending_map)
            route_rows = merge_routes(route_rows, pending_routes)
            save_outputs(mapping_rows, route_rows)
            pending_map.clear(); pending_routes.clear()
            CATALOGUE_CHECKPOINT_PATH.write_text(json.dumps({
                "updated_at": now_iso(), "done_ids": sorted(done_ids), "stats": stats
            }, indent=2), encoding="utf-8")
            report = coverage_report(db_path, route_rows, mapping_rows)
            print(f"Catalogue progress {len(done_ids)}/{len(ids)} discovered IDs | "
                  f"mapped={report['mapped_to_nqr_id']}/{report['unique_qualification_codes']} | "
                  f"eligibility={report['eligibility_coverage_percentage']}%")
        time.sleep(args.delay)

    mapping_rows = merge_mapping(mapping_rows, pending_map)
    route_rows = merge_routes(route_rows, pending_routes)
    save_outputs(mapping_rows, route_rows)
    CATALOGUE_CHECKPOINT_PATH.write_text(json.dumps({
        "updated_at": now_iso(), "done_ids": sorted(done_ids), "stats": stats
    }, indent=2), encoding="utf-8")
    report = coverage_report(db_path, route_rows, mapping_rows)
    print("\nFinal catalogue coverage:")
    print(json.dumps(report, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Harvest official NQR eligibility routes into SkillMitra")
    p.add_argument("--db", default=str(DB_PATH))
    p.add_argument("--mapping", default=str(MAPPING_CSV))
    p.add_argument("--routes", default=str(ROUTES_CSV))
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=float, default=20.0)
    common.add_argument("--delay", type=float, default=0.20, help="Polite delay between NQR requests")

    k = sub.add_parser("harvest-known", parents=[common], help="Refresh eligibility for already mapped NQR IDs")
    k.set_defaults(func=harvest_known)

    d = sub.add_parser("discover", parents=[common], help="Discover NQR IDs by scanning a resumable ID range")
    d.add_argument("--start-id", type=int, default=1)
    d.add_argument("--end-id", type=int, default=16000)
    d.add_argument("--flush-every", type=int, default=25)
    d.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    d.add_argument("--skip-known", action=argparse.BooleanOptionalAction, default=True)
    d.set_defaults(func=discover)

    c = sub.add_parser("discover-catalogue", parents=[common], help="Discover real NQR links from official catalogue/sitemaps, then harvest them")
    c.add_argument("--max-sector-id", type=int, default=80, help="Upper bound for NQR sector/category catalogue paths")
    c.add_argument("--flush-every", type=int, default=25)
    c.add_argument("--refresh-ids", action=argparse.BooleanOptionalAction, default=False)
    c.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    c.add_argument("--skip-known", action=argparse.BooleanOptionalAction, default=True)
    c.set_defaults(func=discover_catalogue)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
