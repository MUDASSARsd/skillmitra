@echo off
setlocal
cd /d "%~dp0"
echo Cleaning generated caches and old version-report clutter...
for /d /r %%D in (__pycache__) do @if exist "%%D" rd /s /q "%%D"
for /d /r %%D in (.pytest_cache) do @if exist "%%D" rd /s /q "%%D"
del /s /q *.pyc 2>nul
del /q V*.md V*.json PHASE*_REPORT.md PHASE*_OFFLINE_VOICE.md STABILITY_TEST_REPORT.md JOBS_DEMAND_V17.md NQR_ID_SEED_V15_2.md TRAINING_CENTRES_V16.md SEMANTIC_MAPPING_V13.md 2>nul
del /q test_search.py test_search1.py inspect_page.py inspect_excel.py build_mapping_test.py PASTE_API_KEY_HERE.txt 2>nul
echo Cleanup complete. Runtime/data/source files were preserved.
pause
