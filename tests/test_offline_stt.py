import os, tempfile, unittest, wave
from pathlib import Path
from unittest.mock import patch, Mock
from backend.stt_local import LocalSTT

class TestLocalSTT(unittest.TestCase):
    def wav(self):
        f=tempfile.NamedTemporaryFile(suffix='.wav',delete=False); f.close()
        with wave.open(f.name,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\x00\x00'*1600)
        return Path(f.name)

    def test_not_ready_without_engines(self):
        with patch.dict(os.environ,{},clear=True), patch('backend.stt_local.importlib.util.find_spec', return_value=None):
            self.assertFalse(LocalSTT().status().ready)

    def test_ready_with_whisper_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)/'whisper';m=Path(d)/'model.bin';b.write_text('x');m.write_text('x')
            with patch.dict(os.environ,{},clear=True):
                self.assertTrue(LocalSTT(str(b),str(m)).status().ready)

    def test_valid_wav(self):
        p=self.wav(); LocalSTT.validate_wav(p); p.unlink()

    def test_whisper_fallback_returns_engine(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)/'whisper';m=Path(d)/'model.bin';b.write_text('x');m.write_text('x');p=self.wav()
            Path(str(p)+'.txt').write_text('namaste electrician',encoding='utf8')
            with patch.dict(os.environ,{},clear=True), patch('backend.stt_local.importlib.util.find_spec', return_value=None), patch('backend.stt_local.subprocess.run',return_value=Mock(returncode=0,stdout='',stderr='')):
                text, engine=LocalSTT(str(b),str(m)).transcribe(p,'hi')
                self.assertEqual(text,'namaste electrician'); self.assertEqual(engine,'whisper.cpp-fallback')
            Path(str(p)+'.txt').unlink();p.unlink()

if __name__=='__main__': unittest.main()
