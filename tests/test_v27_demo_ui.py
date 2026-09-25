from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v27_ui_exposes_full_evidence_view():
    html=(ROOT/'frontend'/'index.html').read_text(encoding='utf-8')
    js=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
    assert 'demoStrip' in html
    assert 'evidenceSummary' in html
    assert '/recommend/with-opportunities' in js
    assert 'Full evidence view ready.' in js
    assert 'Skill evidence' in js
    assert 'Live training batch' in js
    assert 'Jobs & salary' in js
    assert 'Career progression' in js

def test_v27_ui_keeps_truth_caveats():
    js=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
    assert 'profile evidence coverage' in js
    assert 'not a competency score' in js
    assert 'No verified live batch in the local snapshot.' in js
