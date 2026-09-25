# SkillMitra Official NQR Eligibility Pipeline

This module improves eligibility coverage using only official National Qualification Register (NQR) pages.

## Safety / correctness rules
- Each NQR eligibility row is stored as a separate **OR route**.
- No LLM is used to invent eligibility.
- Every harvested route stores its NQR source URL, raw text, fetch time, and verification status.
- Existing recommendation/semantic mapping is not modified.
- Discovery is resumable with `data/eligibility_harvest_checkpoint.json`.

## Fast start on Windows
From the project root:

```bat
BUILD_ELIGIBILITY_COVERAGE.bat
```

For a small test first:

```powershell
& "C:\Users\Sanjana\Documents\indic_asr_test\venv312\Scripts\python.exe" scripts\nqr_eligibility_harvester.py discover --start-id 1280 --end-id 1300 --no-resume --no-skip-known
```

Then import what was collected:

```powershell
& "C:\Users\Sanjana\Documents\indic_asr_test\venv312\Scripts\python.exe" scripts\import_eligibility.py
```

## Outputs
- `qualification_mapping.csv` — official NQR ID ↔ local qualification code mapping
- `eligibility_routes.csv` — all alternative entry routes
- `data/eligibility_harvest_checkpoint.json` — resume state
- `data/eligibility_coverage_report.json` — measured coverage
- `data/eligibility_import_report.json` — SQLite import metrics

## Why discovery scans IDs
The local NQR export contains the qualification catalogue and codes but does not currently contain the NQR page ID for every row. The discovery crawler visits qualification pages, extracts the official qualification code, and only keeps pages whose code matches the local 2,814-item catalogue.

The scan is intentionally resumable. It flushes CSV/checkpoint data frequently, so Ctrl+C does not destroy completed work.

## V15.1 smart catalogue discovery

`BUILD_ELIGIBILITY_COVERAGE.bat` now uses `discover-catalogue` before harvesting. It first looks for actual `/qualifications/<id>` links in official NQR sitemaps, the main qualification catalogue, filter search, and sector/category catalogue pages. The discovered IDs are cached in `data/nqr_discovered_ids.json`, and harvesting progress is checkpointed separately in `data/eligibility_catalogue_checkpoint.json`.

The legacy sequential `discover --start-id ... --end-id ...` mode remains available for diagnostics, but the batch file no longer starts that expensive scan automatically.
