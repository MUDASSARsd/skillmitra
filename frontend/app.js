const $ = (id) => document.getElementById(id);
let profile = null;
let busy = false;
let lastMissingCritical = ['education','livelihood_signal','experience','employment_preference','location','training_willingness'];



// ---- Fast multilingual local STT; optional Parakeet / AI4Bharat fallbacks ----
let offlineRecorder = null;
let offlineSTTReady = false;
let offlineSTTStatus = {ready:false, english_ready:false, indic_ready:false, whisper_fallback_ready:false};

function selectedOfflineSTTReady(){
  const lang=($('language')?.value || 'en').toLowerCase();
  const engine=offlineSTTStatus?.language_engines?.[lang];
  if(engine) return engine!=='not installed';
  // Backward-compatible fallback for older status payloads.
  if(lang==='en') return !!(offlineSTTStatus.english_ready || offlineSTTStatus.whisper_fallback_ready);
  if(['hi','hinglish','te','ta','kn','ml','mr','bn','gu','pa','or'].includes(lang))
    return !!(offlineSTTStatus.indic_ready || offlineSTTStatus.whisper_fallback_ready);
  return !!offlineSTTStatus.whisper_fallback_ready;
}

async function refreshOfflineSTT(){
  try{
    const r=await fetch('/stt/offline/status'); const d=await r.json();
    offlineSTTStatus=d||offlineSTTStatus;
    offlineSTTReady=selectedOfflineSTTReady();
    const lang=$('language')?.value || 'en';
    if($('mode')?.value==='offline'){
      if(offlineSTTReady){
        const engine=d?.language_engines?.[lang] || (d.faster_whisper_ready ? 'Whisper fallback' : 'local ASR');
        if($('voiceModeText')) $('voiceModeText').textContent=`Offline ${languageLabel()} microphone ready: ${engine}. No cloud call.`;
      }else{
        const need=`${languageLabel()} high-accuracy Offline speech pack is not installed. Run SETUP_ALL_OFFLINE_LANGUAGES.bat once for every language.`;
        if($('voiceModeText')) $('voiceModeText').textContent=need;
      }
    }
    return offlineSTTReady;
  }catch{
    offlineSTTReady=false;
    offlineSTTStatus={ready:false,english_ready:false,indic_ready:false,whisper_fallback_ready:false};
    if($('mode')?.value==='offline') if($('voiceModeText')) $('voiceModeText').textContent='Offline text works. Could not check local voice-input status.';
    return false;
  }
}
function encodeWav16k(chunks, inputRate){
  const n=chunks.reduce((a,c)=>a+c.length,0), merged=new Float32Array(n); let o=0;
  for(const c of chunks){merged.set(c,o);o+=c.length;}
  const targetRate=16000;
  const outLen=Math.max(1,Math.round(merged.length*targetRate/inputRate));
  const pcm=new Int16Array(outLen);
  for(let i=0;i<outLen;i++){
    const pos=i*inputRate/targetRate;
    const i0=Math.floor(pos), i1=Math.min(merged.length-1,i0+1), frac=pos-i0;
    let sample=(merged[i0]||0)*(1-frac)+(merged[i1]||0)*frac;
    // Small safety limiter; preserve consonants instead of box-averaging them away.
    sample=Math.max(-1,Math.min(1,sample));
    pcm[i]=sample<0?Math.round(sample*0x8000):Math.round(sample*0x7fff);
  }
  const b=new ArrayBuffer(44+pcm.length*2), v=new DataView(b), w=(p,x)=>{for(let i=0;i<x.length;i++)v.setUint8(p+i,x.charCodeAt(i));};
  w(0,'RIFF');v.setUint32(4,36+pcm.length*2,true);w(8,'WAVE');w(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,targetRate,true);v.setUint32(28,targetRate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,'data');v.setUint32(40,pcm.length*2,true);
  for(let i=0;i<pcm.length;i++)v.setInt16(44+i*2,pcm[i],true); return new Blob([b],{type:'audio/wav'});
}
async function startOfflineRecording(target='offline'){
  if(target==='offline' && !offlineSTTReady){$('voiceStatus').textContent='Local STT is not configured for the selected language.';return;}
  if(!navigator.mediaDevices?.getUserMedia){$('voiceStatus').textContent='This browser does not provide microphone access.';return;}

  // Never record the assistant's own previous reply into the next user turn.
  stopAllAudio();
  await unlockAudioOutput();

  const stream=await navigator.mediaDevices.getUserMedia({
    audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}
  });
  const AudioCtx=(window.AudioContext||window.webkitAudioContext);
  let ctx;
  try{ctx=new AudioCtx({sampleRate:16000});}catch(_){ctx=new AudioCtx();}
  if(ctx.state==='suspended') await ctx.resume();

  const source=ctx.createMediaStreamSource(stream);
  const processor=ctx.createScriptProcessor(4096,1,1);
  const silentGain=ctx.createGain();
  silentGain.gain.value=0;
  const chunks=[];

  processor.onaudioprocess=e=>{
    const data=e.inputBuffer.getChannelData(0);
    if(data?.length) chunks.push(new Float32Array(data));
  };

  source.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(ctx.destination);

  offlineRecorder={stream,ctx,source,processor,silentGain,chunks,rate:ctx.sampleRate,startedAt:Date.now(),target};
  setListening(true);
  $('voiceStatus').textContent=target==='online'
    ? `Recording ${languageLabel()}… speak naturally, then tap the mic again to stop.`
    : 'Recording locally… speak now, then tap the mic again to stop.';
}

async function stopOfflineRecording(){
  const r=offlineRecorder;
  if(!r)return;

  // Give AudioContext a moment to deliver the first buffers. This prevents
  // one-sample/empty WAV files that crash IndicConformer preprocessing.
  const minimumSamples=Math.floor(r.rate*0.35);
  const deadline=Date.now()+900;
  const sampleCount=()=>r.chunks.reduce((n,c)=>n+c.length,0);
  while(sampleCount()<minimumSamples && Date.now()<deadline){
    await new Promise(resolve=>setTimeout(resolve,80));
  }

  try{r.processor.disconnect();}catch(_){}
  try{r.source.disconnect();}catch(_){}
  try{r.silentGain?.disconnect();}catch(_){}
  try{r.stream.getTracks().forEach(t=>t.stop());}catch(_){}
  try{await r.ctx.close();}catch(_){}
  offlineRecorder=null;
  setListening(false);

  const captured=sampleCount();
  if(captured<minimumSamples){
    $('voiceStatus').textContent='No usable speech was captured. Tap the mic, speak for at least 1 second, then tap again.';
    return;
  }

  const wav=encodeWav16k(r.chunks,r.rate);
  if(wav.size<1600){
    $('voiceStatus').textContent='Recording was too short. Please speak for at least 1 second and try again.';
    return;
  }

  const target=r.target||'offline';
  $('voiceStatus').textContent=(target==='online')?'Fast online transcription…':(target==='online-local-first'?'Transcribing locally for fast Online AI…':'Transcribing locally…');

  const postRecording=async(url)=>{
    const fd=new FormData();
    fd.append('audio',wav,'speech.wav');
    fd.append('language',$('language').value);
    if(url==='/stt/offline' && lastMissingCritical?.length) fd.append('expected_field',String(lastMissingCritical[0]||''));
    const res=await fetch(url,{method:'POST',body:fd});
    const d=await res.json().catch(()=>({}));
    if(!res.ok)throw new Error(d.detail||(url==='/stt/online'?'Online transcription failed':'Local transcription failed'));
    return d;
  };

  try{
    let d, usedLocalFallback=false;
    if(target==='online-local-first'){
      // Online mode can still use local STT. Only the reasoning/recommendation
      // needs to be online, so this avoids a slow audio upload on every turn.
      try{
        d=await postRecording('/stt/offline');
        usedLocalFallback=true;
      }catch(localErr){
        d=await postRecording('/stt/online');
        usedLocalFallback=false;
      }
    }else if(target==='online'){
      try{
        d=await postRecording('/stt/online');
      }catch(onlineErr){
        await refreshOfflineSTT();
        if(selectedOfflineSTTReady()){
          d=await postRecording('/stt/offline');
          usedLocalFallback=true;
        }else{
          throw onlineErr;
        }
      }
    }else{
      d=await postRecording('/stt/offline');
    }
    const transcript=(d.text||'').trim();
    if(!transcript){
      $('voiceStatus').textContent='I could not hear clear speech. Please try again and speak a little louder.';
      return;
    }
    $('messageInput').value=transcript;
    // Voice is a hands-free conversation path: once speech has been transcribed,
    // immediately submit the text through the same chat/NQR pipeline. Requiring a
    // second manual Send click made the app look stuck during jury demos.
    $('voiceStatus').textContent=target==='online-local-first'
      ? 'Fast local multilingual transcription complete. Sending to Online AI…'
      : target==='online'
        ? (usedLocalFallback ? 'Fast local multilingual transcription complete. Sending to Online AI…' : 'Voice understood. Sending…')
        : 'Voice understood offline. Processing locally…';
    await submitVoiceTranscript(transcript);
  }catch(e){
    $('voiceStatus').textContent=`Voice input issue: ${e.message}`;
  }
}

async function submitVoiceTranscript(transcript){
  const text=String(transcript||'').trim();
  if(!text) return;
  const input=$('messageInput');
  const form=$('chatForm');
  if(!input || !form) return;
  input.value=text;
  // Yield once so the recognised sentence is visible before the response starts.
  await new Promise(resolve=>setTimeout(resolve,40));
  if(typeof form.requestSubmit==='function') form.requestSubmit();
  else form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
}

// ---- Phase 9: browser + local voice input/output ----
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let recognitionHadError = false;
let recognitionFinalText = '';
let listening = false;

const SPEECH_LOCALES = {
  en:'en-IN', hi:'hi-IN', hinglish:'hi-IN', te:'te-IN', ta:'ta-IN', kn:'kn-IN',
  ml:'ml-IN', mr:'mr-IN', bn:'bn-IN', gu:'gu-IN', pa:'pa-IN', or:'or-IN'
};
const LANGUAGE_LABELS = {
  en:'English', hi:'Hindi', hinglish:'Hinglish', te:'Telugu', ta:'Tamil', kn:'Kannada',
  ml:'Malayalam', mr:'Marathi', bn:'Bengali', gu:'Gujarati', pa:'Punjabi', or:'Odia'
};
function selectedLanguage(){ return ($('language')?.value || 'en').toLowerCase(); }
function speechLang(){
  const lang=selectedLanguage();
  if(lang==='hi'||lang==='hinglish') return 'hi-IN';
  if(lang==='te') return 'te-IN';
  if(lang==='en') return 'en-IN';
  return SPEECH_LOCALES[lang] || 'en-IN';
}
function languageLabel(){ return LANGUAGE_LABELS[selectedLanguage()] || selectedLanguage(); }
function updateVoiceModeText(){
  if(!$('voiceModeText')) return;
  if($('mode')?.value==='offline'){
    $('voiceModeText').textContent='Offline local NLU + local ASR routing is active. Voice audio stays on this device.';
  }else{
    $('voiceModeText').textContent=`Online ${languageLabel()} microphone uses low-latency cloud transcription. Local ASR is not used in Online mode.`;
  }
}
// Never silently fall back to an unrelated installed voice.
function findVoiceFor(lang){
  if(!('speechSynthesis' in window)) return null;
  const target=String(lang||'').toLowerCase();
  const base=target.split('-')[0];
  const voices=window.speechSynthesis.getVoices();
  return voices.find(v=>String(v.lang||'').toLowerCase()===target)
      || voices.find(v=>String(v.lang||'').toLowerCase().startsWith(base+'-'))
      || voices.find(v=>String(v.lang||'').toLowerCase()===base)
      || null;
}
let activeAudio = null;
let ttsAudioContext = null;
let activeAudioSource = null;
let ttsAudioPrimed = false;

function stopAllAudio(){
  if(activeAudio){
    try{
      activeAudio.pause();
      activeAudio.currentTime = 0;
      activeAudio.src = '';
    }catch(_){}
    activeAudio = null;
  }
  if(activeAudioSource){
    try{
      activeAudioSource.stop();
      activeAudioSource.disconnect();
    }catch(_){}
    activeAudioSource = null;
  }
  try{ window.speechSynthesis?.cancel(); }catch(_){}
}

async function unlockAudioOutput(){
  try{
    if(!ttsAudioContext){
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if(Ctx) ttsAudioContext = new Ctx();
    }
    if(ttsAudioContext?.state === 'suspended') await ttsAudioContext.resume();
    // Prime the output while we are still inside a real user gesture (mic/send/toggle).
    if(ttsAudioContext && !ttsAudioPrimed){
      const buffer = ttsAudioContext.createBuffer(1, 1, ttsAudioContext.sampleRate);
      const source = ttsAudioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(ttsAudioContext.destination);
      source.start(0);
      ttsAudioPrimed = true;
    }
  }catch(_){}
}

function cleanSpeechText(text){
  let t = String(text || '');
  t = t.replace(/\*\*([^*]+)\*\*/g, '$1');
  t = t.replace(/\*([^*]+)\*/g, '$1');
  t = t.replace(/__([^_]+)__/g, '$1');
  t = t.replace(/_([^_]+)_/g, '$1');
  t = t.replace(/^[\s*•\-#]+\s*/gm, '');
  t = t.replace(/[\s*•\-#]+/g, ' ');
  t = t.replace(/\s*\/\s*/g, ' ');
  t = t.replace(/[~^<>\"`@$%&]+/g, ' ');
  return t.replace(/\s+/g, ' ').trim();
}

async function playAudioResponse(url, options={}){
  stopAllAudio();
  const r = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(options)
  });
  if(!r.ok){
    const d = await r.json().catch(() => ({}));
    throw new Error(d.detail || 'Speech service unavailable');
  }

  const blob = await r.blob();
  if(!blob.size) throw new Error('Speech service returned empty audio');

  const objectUrl = URL.createObjectURL(blob);
  const audio = new Audio();
  activeAudio=audio;

  let cleaned = false;
  const cleanup = () => {
    if(cleaned) return;
    cleaned = true;
    setTimeout(() => { try{ URL.revokeObjectURL(objectUrl); }catch(_){} }, 15000);
    if(activeAudio === audio) activeAudio = null;
  };
  audio.onended = cleanup;
  audio.onerror = cleanup;

  try{
    audio.src = objectUrl;
    await audio.play();
    return;
  }catch(playErr){
    cleanup();
    // Fallback: If HTML5 Audio was blocked by autoplay or driver issue, try WebAudio
    try{
      await unlockAudioOutput();
      if(ttsAudioContext){
        const arrayBuf = await blob.arrayBuffer();
        const decoded = await ttsAudioContext.decodeAudioData(arrayBuf);
        stopAllAudio();
        const source = ttsAudioContext.createBufferSource();
        source.buffer = decoded;
        source.connect(ttsAudioContext.destination);
        activeAudioSource = source;
        source.onended = () => {
          if(activeAudioSource === source){
            try{ source.disconnect(); }catch(_){}
            activeAudioSource = null;
          }
        };
        source.start(0);
        return;
      }
    }catch(_){}
    throw playErr;
  }
}

async function speak(text){
  if(!$('speakToggle')?.checked || !text) return;
  const cleanedText = cleanSpeechText(text) || text;
  const lang = speechLang();
  const code = selectedLanguage();
  const label = languageLabel();
  const voice = findVoiceFor(lang);

  stopAllAudio();

  if($('mode')?.value==='offline'){
    if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label}…`;
    // Try the smooth online neural audio first ONLY when internet is actually connected:
    if(navigator.onLine){
      try{
        await playAudioResponse('/tts/online',{text,language:code});
        if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label}.`;
        return;
      }catch(_){}
    }
    // Fully offline path: local WAV backend (Piper / eSpeak NG)
    try{
        await playAudioResponse('/tts/offline',{text,language:code});
        if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label} offline.`;
        return;
      }catch(browserErr){
        stopAllAudio();
        try{
          const direct = await fetch('/tts/offline/play-local', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: cleanedText, language: code})
          });
          if(direct.ok){
            if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label} offline (Windows speaker).`;
            return;
          }
          const detail = await direct.json().catch(() => ({}));
          throw new Error(detail.detail || browserErr.message || 'Local speaker playback failed');
        }catch(directErr){
          stopAllAudio();
          if('speechSynthesis' in window && voice){
            try{
              window.speechSynthesis.cancel();
              const utterance = new SpeechSynthesisUtterance(cleanedText);
              window._activeUtterance = utterance;
              utterance.onend = () => { window._activeUtterance = null; };
              utterance.lang = lang;
              utterance.voice = voice;
              utterance.rate = 0.95;
              window.speechSynthesis.speak(utterance);
              if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label} with system fallback.`;
              return;
            }catch(_){}
          }
          if($('voiceStatus')) $('voiceStatus').textContent = `Offline ${label} speech failed: ${directErr.message}`;
          return;
        }
      }
    }

  // In Online mode, prioritize clear Edge Neural TTS first for crystal-clear, smooth natural voice.
  try{
    if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label}…`;
    await playAudioResponse('/tts/online',{text,language:code});
    if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label}.`;
    return;
  }catch(onlineErr){
    // Fallback 1: Local offline speech
    const localPiperLang = code === 'hinglish' ? 'hi' : code;
    try{
      await playAudioResponse('/tts/offline',{text,language:localPiperLang});
      if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label} with local fallback.`;
      return;
    }catch(_){}

    // Fallback 2: Browser SpeechSynthesis with GC-protection to prevent freezing
    if('speechSynthesis' in window && voice){
      try{
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleanedText);
        window._activeUtterance = utterance;
        utterance.onend = () => { window._activeUtterance = null; };
        utterance.lang = lang;
        utterance.voice = voice;
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
        if($('voiceStatus')) $('voiceStatus').textContent = `Speaking ${label} with system fallback.`;
        return;
      }catch(_){}
    }
    if($('voiceStatus')) $('voiceStatus').textContent = `${label} text reply is available; online speech is unavailable: ${onlineErr.message}`;
  }
}

async function reportTTSAvailability(){
  const lang=speechLang();
  const code=selectedLanguage();
  const label=languageLabel();
  const voice=findVoiceFor(lang);
  if(!$('voiceStatus') || !$('speakToggle')?.checked) return;

  // In Offline mode report the explicit local backend first, matching speak().
  if($('mode')?.value==='offline'){
    try{
      const r=await fetch('/tts/offline/status');
      const d=await r.json();
      const info=d.languages?.[code] || (code==='hinglish' ? d.languages?.hi : null);
      $('voiceStatus').textContent=info?.ready
        ? `Local ${label} speech ready (${info.engine}).`
        : (voice ? `Local backend is not ready; system ${label} voice is available as fallback.`
                 : `Offline ${label} text works; run SETUP_OFFLINE_TTS.bat once for local speech.`);
      return;
    }catch(_){
      $('voiceStatus').textContent=voice
        ? `Local backend status unavailable; system ${label} voice is available as fallback.`
        : `Offline ${label} text works; local speech status is unavailable.`;
      return;
    }
  }

  if(voice){
    $('voiceStatus').textContent=`Speech voice ready: ${voice.name} (${voice.lang})`;
    return;
  }
  try{
    const r=await fetch('/tts/online/status');
    const d=await r.json();
    $('voiceStatus').textContent=d.ready
      ? `Online ${label} neural voice ready.`
      : `${label} text works. Run UPDATE_VOICE_SUPPORT.bat once to enable online speech.`;
  }catch(_){
    $('voiceStatus').textContent=`${label} text works; online speech status is unavailable.`;
  }
}

if('speechSynthesis' in window){
  window.speechSynthesis.onvoiceschanged=()=>reportTTSAvailability();
}
$('speakToggle')?.addEventListener('change',async()=>{await unlockAudioOutput(); setTimeout(reportTTSAvailability,50);});
function setListening(v){
  listening=v;
  const btn=$('micBtn');
  if(!btn) return;
  btn.classList.toggle('listening',v);
  btn.textContent=v?'⏹️':'🎙️';
  btn.setAttribute('aria-label',v?'Stop voice input':'Start voice input');
}
async function resetVoiceCapture(){
  if(offlineRecorder){
    try{offlineRecorder.processor?.disconnect();}catch(_){}
    try{offlineRecorder.source?.disconnect();}catch(_){}
    try{offlineRecorder.silentGain?.disconnect();}catch(_){}
    try{offlineRecorder.stream?.getTracks()?.forEach(t=>t.stop());}catch(_){}
    try{if(offlineRecorder.ctx && offlineRecorder.ctx.state!=='closed') await offlineRecorder.ctx.close();}catch(_){}
    offlineRecorder=null;
  }
  if(recognition){try{recognition.abort();}catch(_){} recognition=null;}
  recognitionHadError=false;
  recognitionFinalText='';
  setListening(false);
  if($('micBtn')) $('micBtn').disabled=false;
}

function attachRecognitionHandlers(rec){
  recognitionHadError=false;
  recognitionFinalText='';
  rec.continuous=false;
  rec.interimResults=true;
  rec.maxAlternatives=1;
  rec.lang=speechLang();
  rec.onstart=()=>{setListening(true);$('voiceStatus').textContent='Listening… speak naturally.';};
  rec.onresult=(event)=>{
    let transcript='';
    for(let i=0;i<event.results.length;i++) transcript+=event.results[i][0].transcript;
    recognitionFinalText=transcript.trim();
    $('messageInput').value=recognitionFinalText;
  };
  rec.onerror=(event)=>{
    recognitionHadError=true;
    setListening(false);
    const friendly=event.error==='not-allowed'
      ? 'Microphone permission was blocked. Allow microphone access for this site and try again.'
      : event.error==='language-not-supported'
        ? `${languageLabel()} on-device speech pack is not installed or supported in this browser.`
        : `Voice input error: ${event.error}. You can type instead.`;
    $('voiceStatus').textContent=friendly;
  };
  rec.onend=async()=>{
    setListening(false);
    recognition=null;
    if(!recognitionHadError && recognitionFinalText){
      const captured=recognitionFinalText;
      recognitionFinalText='';
      $('voiceStatus').textContent='Voice understood. Sending…';
      await submitVoiceTranscript(captured);
    }else if(!recognitionHadError){
      $('voiceStatus').textContent='I could not hear clear speech. Please try again.';
    }
  };
}

async function ensureBrowserOfflineSpeech(locale){
  if(!SpeechRecognitionAPI) throw new Error('Speech recognition is not supported by this browser.');
  const probe=new SpeechRecognitionAPI();
  if(!('processLocally' in probe)) throw new Error('This browser does not support on-device speech recognition.');

  // Newer Chromium exposes language-pack availability/install helpers. When they
  // are absent, we can still try processLocally=true and let the browser decide.
  if(typeof SpeechRecognitionAPI.available==='function'){
    const state=await SpeechRecognitionAPI.available({langs:[locale],processLocally:true});
    if(state==='unavailable') throw new Error(`${languageLabel()} on-device speech is unavailable in this browser.`);
    if(state==='downloadable' || state==='downloading'){
      if(typeof SpeechRecognitionAPI.install!=='function') throw new Error(`${languageLabel()} speech pack is not installed.`);
      $('voiceStatus').textContent=`Installing ${languageLabel()} on-device speech pack…`;
      const installed=await SpeechRecognitionAPI.install({langs:[locale],processLocally:true});
      if(!installed) throw new Error(`${languageLabel()} on-device speech pack could not be installed.`);
    }
  }
}

async function startBrowserRecognition(localOnly){
  if(!SpeechRecognitionAPI) throw new Error('Speech recognition is not supported by this browser.');
  const locale=speechLang();
  if(localOnly) await ensureBrowserOfflineSpeech(locale);
  const rec=new SpeechRecognitionAPI();
  attachRecognitionHandlers(rec);
  if('processLocally' in rec) rec.processLocally=!!localOnly;
  else if(localOnly) throw new Error('This browser does not support on-device speech recognition.');
  recognition=rec;
  rec.start();
}

function initVoice(){
  const btn=$('micBtn');
  btn.addEventListener('click',async()=>{
    await unlockAudioOutput();
    if(listening){
      try{
        if(offlineRecorder) await stopOfflineRecording();
        else if(recognition) recognition.stop();
      }catch(e){setListening(false);$('voiceStatus').textContent=`Microphone error: ${e.message}`;}
      return;
    }

    const offline=$('mode')?.value==='offline';
    if(!offline){
      // Online mode must stay online-fast. Capture audio locally, but send it
      // directly to the single-call cloud STT endpoint. Never wait for or load
      // the local Whisper model just because Online AI is selected.
      try{await startOfflineRecording('online');}
      catch(e){setListening(false);$('voiceStatus').textContent=`Microphone error: ${e.message}`;}
      return;
    }

    // Offline mode: first use the project-local ASR backend. If it is not installed,
    // try the browser's true on-device recognition and language pack instead of
    // blocking the microphone before permission is even requested.
    await refreshOfflineSTT();
    if(offlineSTTReady){
      try{await startOfflineRecording();}
      catch(e){setListening(false);$('voiceStatus').textContent=`Microphone error: ${e.message}`;}
      return;
    }

    // Chromium does not provide on-device packs for several Indic locales.
    // For the multilingual demo, give one deterministic setup instruction instead
    // of sending Telugu/Tamil/etc. into an unavailable browser pack.
    if(selectedLanguage()!=='en'){
      setListening(false);
      $('voiceStatus').textContent=`${languageLabel()} offline microphone setup is required. Run SETUP_FAST_MULTILINGUAL_MIC.bat once, restart the app, then try again.`;
      return;
    }
    try{
      await startBrowserRecognition(true);
    }catch(e){
      setListening(false);
      $('voiceStatus').textContent=`English offline microphone is unavailable. Run SETUP_FAST_MULTILINGUAL_MIC.bat once.`;
    }
  });
}

const UI_TEXT = {
  en: {greet:'Namaste 👋\nTell me about your education, skills, work experience, and the kind of work you are interested in. You can answer naturally.', ready:'I have enough information to suggest relevant NQR pathways. I have shown the matches below.', noMatch:'Your profile is ready, but I could not find a strong NQR match for the current work signal. Please describe the work or skill in a little more detail.'},
  hi: {greet:'नमस्ते 👋\nअपनी पढ़ाई, कौशल, काम के अनुभव और किस तरह का काम करना चाहते हैं, उसके बारे में बताइए। आप स्वाभाविक रूप से बोल सकते हैं।', ready:'मेरे पास संबंधित NQR विकल्प सुझाने के लिए पर्याप्त जानकारी है। नीचे मिलते-जुलते विकल्प दिखाए गए हैं।', noMatch:'आपकी प्रोफ़ाइल तैयार है, लेकिन अभी मजबूत NQR मिलान नहीं मिला। कृपया अपने काम या कौशल को थोड़ा और स्पष्ट बताइए।'},
  hinglish: {greet:'Namaste 👋\nApni education, skills, work experience aur kis tarah ka kaam karna chahte hain, naturally bataiye.', ready:'Mere paas relevant NQR pathways suggest karne ke liye enough information hai. Matches neeche dikhaye gaye hain.', noMatch:'Profile ready hai, lekin strong NQR match nahi mila. Apna kaam ya skill thoda aur clearly bataiye.'},
  te: {greet:'నమస్తే 👋\nమీ చదువు, నైపుణ్యాలు, పని అనుభవం మరియు మీరు చేయాలనుకునే పని గురించి సహజంగా చెప్పండి.', ready:'సంబంధిత NQR మార్గాలను సూచించడానికి కావలసిన సమాచారం వచ్చింది. సరిపోలిన ఎంపికలు క్రింద చూపించాను.', noMatch:'మీ ప్రొఫైల్ సిద్ధంగా ఉంది, కానీ ప్రస్తుతం బలమైన NQR సరిపోలిక దొరకలేదు. మీ పని లేదా నైపుణ్యాన్ని కొంచెం స్పష్టంగా చెప్పండి.'},
  ta: {greet:'வணக்கம் 👋\nஉங்கள் கல்வி, திறன்கள், வேலை அனுபவம் மற்றும் நீங்கள் விரும்பும் வேலை பற்றி இயல்பாக சொல்லுங்கள்.', ready:'தொடர்புடைய NQR பாதைகளை பரிந்துரைக்க போதுமான தகவல் கிடைத்துள்ளது. பொருந்தும் விருப்பங்கள் கீழே காட்டப்பட்டுள்ளன.', noMatch:'உங்கள் சுயவிவரம் தயாராக உள்ளது, ஆனால் இப்போது வலுவான NQR பொருத்தம் கிடைக்கவில்லை. உங்கள் வேலை அல்லது திறனை இன்னும் கொஞ்சம் தெளிவாக சொல்லுங்கள்.'},
  kn: {greet:'ನಮಸ್ಕಾರ 👋\nನಿಮ್ಮ ಶಿಕ್ಷಣ, ಕೌಶಲ್ಯಗಳು, ಕೆಲಸದ ಅನುಭವ ಮತ್ತು ನೀವು ಮಾಡಲು ಬಯಸುವ ಕೆಲಸದ ಬಗ್ಗೆ ಸಹಜವಾಗಿ ಹೇಳಿ.', ready:'ಸಂಬಂಧಿತ NQR ಮಾರ್ಗಗಳನ್ನು ಸೂಚಿಸಲು ಸಾಕಷ್ಟು ಮಾಹಿತಿ ದೊರೆತಿದೆ. ಹೊಂದುವ ಆಯ್ಕೆಗಳನ್ನು ಕೆಳಗೆ ತೋರಿಸಲಾಗಿದೆ.', noMatch:'ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ಸಿದ್ಧವಾಗಿದೆ, ಆದರೆ ಈಗ ಬಲವಾದ NQR ಹೊಂದಾಣಿಕೆ ಸಿಗಲಿಲ್ಲ. ನಿಮ್ಮ ಕೆಲಸ ಅಥವಾ ಕೌಶಲ್ಯವನ್ನು ಇನ್ನಷ್ಟು ಸ್ಪಷ್ಟವಾಗಿ ವಿವರಿಸಿ.'},
  ml: {greet:'നമസ്കാരം 👋\nനിങ്ങളുടെ വിദ്യാഭ്യാസം, കഴിവുകൾ, ജോലി പരിചയം, നിങ്ങൾ ആഗ്രഹിക്കുന്ന ജോലി എന്നിവയെ കുറിച്ച് സ്വാഭാവികമായി പറയൂ.', ready:'ബന്ധപ്പെട്ട NQR മാർഗങ്ങൾ നിർദ്ദേശിക്കാൻ മതിയായ വിവരം ലഭിച്ചു. പൊരുത്തപ്പെടുന്ന ഓപ്ഷനുകൾ താഴെ കാണിച്ചിരിക്കുന്നു.', noMatch:'നിങ്ങളുടെ പ്രൊഫൈൽ തയ്യാറാണ്, പക്ഷേ ഇപ്പോൾ ശക്തമായ NQR പൊരുത്തം കണ്ടെത്താനായില്ല. നിങ്ങളുടെ ജോലി അല്ലെങ്കിൽ കഴിവ് കുറച്ച് കൂടുതൽ വിശദമായി പറയൂ.'},
  mr: {greet:'नमस्कार 👋\nतुमचे शिक्षण, कौशल्ये, कामाचा अनुभव आणि तुम्हाला कोणते काम करायचे आहे याबद्दल नैसर्गिकपणे सांगा.', ready:'संबंधित NQR मार्ग सुचवण्यासाठी पुरेशी माहिती मिळाली आहे. जुळणारे पर्याय खाली दाखवले आहेत.', noMatch:'तुमची प्रोफाइल तयार आहे, पण सध्या मजबूत NQR जुळणी मिळाली नाही. तुमचे काम किंवा कौशल्य थोडे अधिक स्पष्ट सांगा.'},
  bn: {greet:'নমস্কার 👋\nআপনার শিক্ষা, দক্ষতা, কাজের অভিজ্ঞতা এবং আপনি কী ধরনের কাজ করতে চান তা স্বাভাবিকভাবে বলুন।', ready:'প্রাসঙ্গিক NQR পথ প্রস্তাব করার জন্য যথেষ্ট তথ্য পাওয়া গেছে। মিল পাওয়া বিকল্পগুলো নিচে দেখানো হয়েছে।', noMatch:'আপনার প্রোফাইল প্রস্তুত, কিন্তু এখন শক্তিশালী NQR মিল পাওয়া যায়নি। আপনার কাজ বা দক্ষতা আরেকটু বিস্তারিত বলুন।'},
  gu: {greet:'નમસ્તે 👋\nતમારું શિક્ષણ, કુશળતા, કામનો અનુભવ અને તમે કયું કામ કરવા માંગો છો તે સ્વાભાવિક રીતે કહો.', ready:'સંબંધિત NQR માર્ગ સૂચવવા માટે પૂરતી માહિતી મળી છે. મેળ ખાતા વિકલ્પો નીચે બતાવ્યા છે.', noMatch:'તમારી પ્રોફાઇલ તૈયાર છે, પરંતુ હાલમાં મજબૂત NQR મેળ મળ્યો નથી. તમારા કામ અથવા કુશળતા વિશે થોડું વધુ સ્પષ્ટ કહો.'},
  pa: {greet:'ਸਤ ਸ੍ਰੀ ਅਕਾਲ 👋\nਆਪਣੀ ਪੜ੍ਹਾਈ, ਹੁਨਰ, ਕੰਮ ਦੇ ਤਜਰਬੇ ਅਤੇ ਤੁਸੀਂ ਕਿਹੜਾ ਕੰਮ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ, ਇਸ ਬਾਰੇ ਸੁਭਾਵਿਕ ਤਰੀਕੇ ਨਾਲ ਦੱਸੋ।', ready:'ਸੰਬੰਧਿਤ NQR ਰਾਹ ਸੁਝਾਉਣ ਲਈ ਕਾਫ਼ੀ ਜਾਣਕਾਰੀ ਮਿਲ ਗਈ ਹੈ। ਮਿਲਦੇ ਵਿਕਲਪ ਹੇਠਾਂ ਦਿਖਾਏ ਗਏ ਹਨ।', noMatch:'ਤੁਹਾਡੀ ਪ੍ਰੋਫ਼ਾਈਲ ਤਿਆਰ ਹੈ, ਪਰ ਇਸ ਵੇਲੇ ਮਜ਼ਬੂਤ NQR ਮੇਲ ਨਹੀਂ ਮਿਲਿਆ। ਆਪਣੇ ਕੰਮ ਜਾਂ ਹੁਨਰ ਬਾਰੇ ਥੋੜ੍ਹਾ ਹੋਰ ਸਪਸ਼ਟ ਦੱਸੋ।'},
  or: {greet:'ନମସ୍କାର 👋\nଆପଣଙ୍କ ଶିକ୍ଷା, କୌଶଳ, କାମର ଅନୁଭବ ଏବଂ କେଉଁ ପ୍ରକାର କାମ କରିବାକୁ ଚାହୁଁଛନ୍ତି ସେ ବିଷୟରେ ସ୍ୱାଭାବିକ ଭାବେ କହନ୍ତୁ।', ready:'ସମ୍ପର୍କିତ NQR ପଥ ସୁପାରିଶ କରିବା ପାଇଁ ପର୍ଯ୍ୟାପ୍ତ ସୂଚନା ମିଳିଛି। ମେଳ ଥିବା ବିକଳ୍ପଗୁଡ଼ିକ ତଳେ ଦେଖାଯାଇଛି।', noMatch:'ଆପଣଙ୍କ ପ୍ରୋଫାଇଲ୍ ପ୍ରସ୍ତୁତ, କିନ୍ତୁ ଏବେ ଶକ୍ତିଶାଳୀ NQR ମେଳ ମିଳିଲା ନାହିଁ। ଆପଣଙ୍କ କାମ କିମ୍ବା କୌଶଳ ବିଷୟରେ ଆଉ କିଛି ସ୍ପଷ୍ଟ କରନ୍ତୁ।'}
};
function selectedText(){return UI_TEXT[$('language')?.value] || UI_TEXT.en;}
function resetGreeting(){
  const t=selectedText();
  $('chat').innerHTML=`<div class="message assistant"><div class="avatar">SM</div><div class="bubble">${esc(t.greet).replace(/\n/g,'<br>')}</div></div>`;
}

const emptyProfile = () => ({education:{level:null,status:null,stream:null},occupation:null,skills:[],interests:[],experience:[],location:{state:null,district:null},employment_preference:null,training_willingness:null,mobility_km:null,language:null});

function esc(v){return String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
function nice(v){if(v===null||v===undefined||v===''||(Array.isArray(v)&&!v.length)) return null; if(Array.isArray(v)) return v.join(', '); return String(v).replaceAll('_',' ');}
function addMessage(text, who='assistant'){
  const div=document.createElement('div'); div.className=`message ${who}`;
  div.innerHTML=`<div class="avatar">${who==='assistant'?'SM':'YOU'}</div><div class="bubble">${esc(text).replace(/\n/g,'<br>')}</div>`;
  $('chat').appendChild(div); $('chat').scrollTop=$('chat').scrollHeight;
}
function setBusy(v){busy=v;$('sendBtn').disabled=v;$('sendBtn').textContent=v?'Thinking…':'Send →';}
function showNotice(msg){$('notice').textContent=msg;$('notice').classList.toggle('hidden',!msg);}

function renderProfile(p=profile){
  const x=p||emptyProfile();
  const exp=(x.experience||[]).map(e=>`${e.domain||'experience'}${e.duration_months!=null?` (${e.duration_months} months)`:''}`).join(', ');
  const rows=[['Education',[x.education?.level,x.education?.status,x.education?.stream].filter(Boolean).join(' · ')],['Occupation',x.occupation],['Skills',nice(x.skills)],['Interests',nice(x.interests)],['Experience',exp],['Location',[x.location?.district,x.location?.state].filter(Boolean).join(', ')],['Work preference',nice(x.employment_preference)],['Training',x.training_willingness===true?'Willing':x.training_willingness===false?'Not willing':null]];
  $('profileGrid').innerHTML=rows.map(([k,v])=>`<div class="profile-row"><span>${k}</span><strong class="${v?'':'empty-value'}">${esc(v||'Not provided')}</strong></div>`).join('');
}
function renderMissing(critical=[], enrichment=[]){
  lastMissingCritical=[...(critical||[])];
  const all=[...critical,...enrichment]; $('missingTags').innerHTML=all.length?all.map(x=>`<span class="tag">${esc(nice(x))}</span>`).join(''):'<span class="tag">Profile is ready for mapping</span>';
}
function eligibilityClass(s){s=String(s);if(s.includes('ELIGIBLE')&&!s.includes('NOT'))return 'good';if(s.includes('NOT_ELIGIBLE'))return 'bad';return 'warn';}
function renderRecommendations(recs=[]){
  $('resultCount').textContent=`${recs.length} result${recs.length===1?'':'s'}`;
  if(!recs.length){$('results').className='results-empty';$('results').innerHTML='<div class="empty-icon">⌁</div><h3>No recommendations yet</h3><p>Once the profile is ready, matching NQR qualifications will appear here.</p>';return;}
  $('results').className='recommendations';
  $('results').innerHTML=recs.map((r,i)=>{const q=r.qualification||{};const status=String(r.eligibility_status||'UNKNOWN');const reasons=(r.reasons||[]).slice(0,3);const warnings=(r.warnings||[]).slice(0,2);const pct=Math.round((r.relevance_score||0)*100);return `<article class="rec"><div class="rec-top"><div><span class="eyebrow">MATCH ${i+1}</span><h3>${esc(q.title||'Qualification')}</h3><div class="meta">${esc(q.sector_name||'Sector not listed')} · NSQF ${esc(q.nsqf_level_numeric??q.level??'—')}</div></div><span class="elig ${eligibilityClass(status)}">${esc(status.replaceAll('_',' '))}</span></div><div class="scheme-badge">🏛️ PM-AJAY GIA Component | Subsidy & Stipend Supported</div>${q.proposed_occupation?`<p><strong>Occupation:</strong> ${esc(q.proposed_occupation)}</p>`:''}${reasons.length?`<ul>${reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}${warnings.length?`<p><strong>Note:</strong> ${warnings.map(esc).join(' ')}</p>`:''}<div class="score" title="Retrieval/ranking heuristic, not a suitability percentage"><i style="width:${Math.max(4,pct)}%"></i></div></article>`;}).join('');
}
async function checkHealth(){
  try{const r=await fetch('/health');const d=await r.json();$('statusPill').className='status online';$('statusText').textContent=`Local DB · ${d.qualification_count||0} NQR`;}
  catch{$('statusPill').className='status offline';$('statusText').textContent='API unavailable';}
}
async function conversation(text){
  const payload={text,current_profile:profile,language_code:$('language').value,include_recommendations:true,top_k:5};
  const endpoint=$('mode')?.value==='offline'?'/conversation/offline':'/conversation';
  const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await r.json(); if(!r.ok) throw new Error(d.detail||'Conversation request failed'); return d;
}


// ---- V27: jury-ready full evidence rendering ----
async function loadReadiness(){
  try{
    const r=await fetch('/system/readiness'); if(!r.ok)return; const d=await r.json();
    $('metricNqr').textContent=d.semantic_mapping?.count ?? '—';
    $('metricEligibility').textContent=d.eligibility?.routes ?? d.eligibility_routes ?? '11k+';
    $('metricJobs').textContent=d.jobs_cache?.active_job_openings ?? d.jobs_cache?.job_openings ?? '—';
    $('metricCourses').textContent=d.courses_cache?.cached_courses ?? '—';
    $('metricCentres').textContent=d.training_cache?.verified_directory_centres ?? d.training_cache?.training_centres ?? '—';
    $('demoHeadline').textContent=d.offline_core_ready ? 'Offline core ready · evidence layers loaded' : 'System partially ready';
  }catch{}
}
function money(v){if(v===null||v===undefined||Number.isNaN(Number(v)))return '—';return `₹${Math.round(Number(v)).toLocaleString('en-IN')}`;}
function shortDate(v){if(!v)return '—';try{return new Date(v).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})}catch{return v}}
function chips(xs=[],limit=5){return (xs||[]).slice(0,limit).map(x=>`<span class="mini-chip">${esc(typeof x==='string'?x:(x.skill||x.title||x.role_text||''))}</span>`).join('');}
function renderEvidenceSummary(d){
  const first=d.results?.[0]||{}; const jd=first.job_demand||{}; const sg=first.skill_gap||{};
  const batches=d.results?.reduce((a,x)=>a+(x.verified_live_batch_count||0),0)||0;
  const courses=d.results?.reduce((a,x)=>a+(x.skill_india_course_count||0),0)||0;
  const schemes=(d.scheme_matches||[]).filter(x=>!String(x.match_status||x.status||'').includes('NOT')).length;
  $('evidenceSummary').classList.remove('hidden');
  $('evidenceSummary').innerHTML=`
    <div class="evidence-kpi"><span>Skill evidence</span><strong>${sg.profile_skill_coverage_percent!=null?Math.round(sg.profile_skill_coverage_percent)+'%':'—'}</strong><small>profile coverage, not competency</small></div>
    <div class="evidence-kpi"><span>Live batches</span><strong>${batches}</strong><small>verified imported observations</small></div>
    <div class="evidence-kpi"><span>Course matches</span><strong>${courses}</strong><small>Skill India catalogue</small></div>
    <div class="evidence-kpi"><span>Job vacancies</span><strong>${jd.total_vacancies??0}</strong><small>${esc(jd.demand_band||'NO DATA')}</small></div>
    <div class="evidence-kpi"><span>Scheme signals</span><strong>${schemes}</strong><small>needs final eligibility verification</small></div>`;
}
function renderOpportunityRecommendations(d){
  const rows=d.results||[]; renderEvidenceSummary(d);
  $('resultCount').textContent=`${rows.length} result${rows.length===1?'':'s'} · evidence enriched`;
  if(!rows.length){renderRecommendations([]);return;}
  $('results').className='recommendations';
  $('results').innerHTML=rows.map((x,i)=>{
    const r=x.recommendation||{}, q=r.qualification||{}, status=String(r.eligibility_status||'UNKNOWN'), pct=Math.round((r.relevance_score||0)*100);
    const sg=x.skill_gap||{}, jd=x.job_demand||{}, course=x.skill_india_courses?.[0], batch=x.verified_live_batches?.[0], job=x.jobs?.[0], cp=x.career_progression||{};
    const missing=sg.priority_gaps||sg.not_evidenced_skills||[];
    const progression=(cp.official_progression_roles||[]).map(v=>v.role_text).filter(Boolean);
    return `<article class="rec">
      <div class="rec-top"><div><span class="eyebrow">PATHWAY ${i+1}</span><h3>${esc(q.title||'Qualification')}</h3><div class="meta">${esc(q.code||'No code')} · ${esc(q.sector_name||'Sector not listed')} · NSQF ${esc(q.nsqf_level_numeric??q.level??'—')}</div></div><span class="elig ${eligibilityClass(status)}">${esc(status.replaceAll('_',' '))}</span></div>
      ${q.proposed_occupation?`<p><strong>Occupation:</strong> ${esc(q.proposed_occupation)}</p>`:''}
      ${(r.reasons||[]).slice(0,2).length?`<ul>${(r.reasons||[]).slice(0,2).map(v=>`<li>${esc(v)}</li>`).join('')}</ul>`:''}
      <div class="score" title="Retrieval/ranking heuristic, not a suitability percentage"><i style="width:${Math.max(4,pct)}%"></i></div>
      <details class="rec-details" ${i===0?'open':''}><summary>View evidence & next steps ▾</summary><div class="evidence-grid">
        <div class="evidence-box"><h4>Skill gap</h4><p><strong>${sg.profile_skill_coverage_percent!=null?Math.round(sg.profile_skill_coverage_percent)+'%':'Unknown'}</strong> profile evidence coverage</p>${missing.length?`<p>Priority: ${chips(missing,4)}</p>`:'<p>No structured gap evidence available.</p>'}</div>
        <div class="evidence-box"><h4>Skill India course</h4>${course?`<p><strong>${esc(course.title||'Course')}</strong></p><p>${esc(course.provider||'Provider not listed')} · ${esc(course.language||'Language n/a')}</p>`:'<p>No cached catalogue match.</p>'}</div>
        <div class="evidence-box"><h4>Live training batch</h4>${batch?`<p><strong>${esc(batch.training_centre||batch.tc_name||batch.TcName||'Verified centre')}</strong></p><p>${esc(batch.district||batch.district_name||batch.DistrictName||'')} ${esc(batch.state||batch.state_name||batch.StateName||'')}</p><p>Starts ${esc(shortDate(batch.batch_start_date||batch.BatchStartDate))}</p>`:'<p>No verified live batch in the local snapshot.</p>'}</div>
        <div class="evidence-box"><h4>Jobs & salary</h4><p><strong>${jd.total_vacancies??0}</strong> vacancies · ${esc(jd.demand_band||'NO DATA')}</p><p>Median: ${money(jd.median_monthly_salary)}/month</p>${job?`<p>${esc(job.title)} · ${esc(job.district||job.state||'location n/a')}</p>`:''}</div>
        <div class="evidence-box"><h4>Career progression</h4>${progression.length?`<p>${chips(progression,4)}</p>`:(cp.official_progression_text?`<p>${esc(cp.official_progression_text)}</p>`:'<p>No official progression text available.</p>')}</div>
        <div class="evidence-box"><h4>Evidence policy</h4><p>Jobs are cached market evidence. Batch availability is shown only when explicitly observed. Skill coverage is not a competency score.</p><p class="source-line">Location scope: ${esc(x.job_location_scope||'none')}</p></div>
      </div></details>
    </article>`;
  }).join('');
  const schemes=(d.scheme_matches||[]).filter(x=>!String(x.match_status||x.status||'').includes('NOT')).slice(0,3);
  if(schemes.length){
    const box=document.createElement('div'); box.className='truth-note'; box.innerHTML=`<strong>Government scheme signals:</strong> ${schemes.map(x=>esc(x.scheme_name||x.name||x.scheme_code||'Scheme')).join(' · ')}. Final eligibility/application must be verified on the official scheme source.`; $('results').appendChild(box);
  }
}
async function enrichProfile(p){
  try{
    $('voiceStatus').textContent='Loading training, jobs, salary, schemes and career evidence…';
    const r=await fetch('/recommend/with-opportunities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:p,top_k:5,candidate_limit:30})});
    const d=await r.json(); if(!r.ok)throw new Error(d.detail||'Evidence enrichment failed');
    renderOpportunityRecommendations(d); $('voiceStatus').textContent='Full evidence view ready.';
  }catch(e){showNotice(`Core recommendation is available. Evidence enrichment issue: ${e.message}`);}
}

const PRESETS = {
  "10th Electrician": "I passed 10th class. I have 1 year of experience working in electrical wiring. I want a job.",
  "Construction Mason": "I passed 8th class. I have 2 years of experience in brick masonry and building construction.",
  "Solar Technician": "I passed 12th class. I want to work in rooftop solar panel installation and renewable energy.",
  "Dairy Farming": "I take care of cows and buffaloes and sell milk. I want dairy farming training."
};
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const key = btn.dataset.preset;
    if (PRESETS[key]) {
      $('messageInput').value = PRESETS[key];
      $('chatForm').dispatchEvent(new Event('submit'));
    }
  });
});
$('chatForm').addEventListener('submit',async e=>{e.preventDefault();await unlockAudioOutput();if(busy)return;const input=$('messageInput');const text=input.value.trim();if(!text)return;addMessage(text,'user');input.value='';showNotice('');setBusy(true);try{const d=await conversation(text);profile=d.profile;renderProfile();renderMissing(d.missing_critical,d.missing_enrichment);if(d.timings_ms?.total!=null){$('voiceStatus').textContent=`Processed in ${(d.timings_ms.total/1000).toFixed(1)}s · ${d.extraction_mode||'NLU'}`;}$('readiness').textContent=d.ready_for_mapping?'Ready to map':'Collecting';$('readiness').className=`badge ${d.ready_for_mapping?'ready':'muted'}`;if(d.next_question){addMessage(d.next_question);await speak(d.next_question);}else if(d.recommendations?.length){const msg=selectedText().ready;addMessage(msg);await speak(msg);}else if(d.ready_for_mapping){const msg=selectedText().noMatch;addMessage(msg);await speak(msg);}renderRecommendations(d.recommendations||[]);if(d.ready_for_mapping && d.recommendations?.length){await enrichProfile(profile);}}catch(err){showNotice(`${err.message}. You can still use the structured offline recommendation demo below.`);}finally{setBusy(false);}});
$('resetBtn').addEventListener('click',async()=>{await resetVoiceCapture();profile=null;resetGreeting();renderProfile();renderMissing(['education','livelihood signal','experience','employment preference','location','training willingness'],[]);renderRecommendations([]);$('evidenceSummary').classList.add('hidden');$('readiness').textContent='Collecting';$('readiness').className='badge muted';showNotice('');});
$('offlineDemoBtn').addEventListener('click',()=>$('offlineDialog').showModal());
$('offlineForm').addEventListener('submit',async e=>{e.preventDefault();const skills=$('offSkills').value.split(',').map(x=>x.trim()).filter(Boolean), interests=$('offInterests').value.split(',').map(x=>x.trim()).filter(Boolean);const months=$('offExpMonths').value;const p=emptyProfile();p.education={level:$('offEducation').value||null,status:$('offStatus').value||null,stream:null};p.skills=skills;p.interests=interests;p.experience=($('offExpDomain').value||months)?[{domain:$('offExpDomain').value||null,duration_months:months===''?null:Number(months)}]:[];p.employment_preference=$('offEmployment').value||null;p.location.district=$('offDistrict').value||null;try{const r=await fetch('/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:p,top_k:5,candidate_limit:30})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Recommendation failed');profile=p;renderProfile();renderRecommendations(d.recommendations||[]);await enrichProfile(profile);$('readiness').textContent='Offline mapped';$('readiness').className='badge ready';$('offlineDialog').close();addMessage('Structured offline profile mapped using the local NQR recommendation engine. No cloud LLM was required.');showNotice('');}catch(err){showNotice(err.message);$('offlineDialog').close();}});
$('mode').addEventListener('change',async()=>{
  await resetVoiceCapture();
  const offline=$('mode').value==='offline';
  updateVoiceModeText();
  showNotice(offline?'Offline local extraction selected: no Gemini/LLM calls will be made.':'');
  await refreshOfflineSTT();
  setTimeout(reportTTSAvailability,150);
});
$('language').addEventListener('change',async()=>{
  await resetVoiceCapture();
  document.documentElement.lang=$('language').value==='hinglish'?'hi':$('language').value;
  if(!profile) resetGreeting();
  updateVoiceModeText();
  await refreshOfflineSTT();
  setTimeout(reportTTSAvailability,150);
});
renderProfile();checkHealth();loadReadiness();updateVoiceModeText();refreshOfflineSTT();initVoice();setTimeout(reportTTSAvailability,250);

// PWA Install prompt handler & Service Worker registration
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = $('installAppBtn');
  if (btn) {
    btn.classList.remove('hidden');
    btn.onclick = async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice;
        if (choice.outcome === 'accepted') {
          btn.classList.add('hidden');
        }
        deferredPrompt = null;
      }
    };
  }
});
window.addEventListener('appinstalled', () => {
  const btn = $('installAppBtn');
  if (btn) btn.classList.add('hidden');
  showNotice('SkillMitra app installed successfully! You can launch it from your home screen or desktop.');
});
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/ui/sw.js').catch(() => {});
  });
}

