from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / 'frontend' / 'app.js').read_text(encoding='utf-8')


def test_voice_transcription_auto_submits():
    assert 'async function submitVoiceTranscript' in JS
    assert "form.requestSubmit()" in JS
    assert "await submitVoiceTranscript(transcript)" in JS


def test_old_review_then_send_loop_removed_from_recorded_audio_path():
    assert 'Offline transcription complete. Review the text, then Send.' not in JS
    assert 'Multilingual cloud transcription complete. Review the text, then Send.' not in JS


def test_browser_voice_also_auto_submits():
    assert 'await submitVoiceTranscript(captured)' in JS
    assert 'Voice understood. Sending…' in JS
