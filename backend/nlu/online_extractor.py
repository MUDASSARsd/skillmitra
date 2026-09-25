"""Online free-form profile extraction using Gemini REST.

Uses requests directly so the app does not depend on the google namespace package.
"""
import os, json, re
from typing import Optional, Callable
import requests
from dotenv import load_dotenv
from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.base import ProfileExtractor
from backend.nlu.local_extractor import LocalProfileExtractor

load_dotenv()

SYSTEM_EXTRACTION_PROMPT = """You are SkillMitra's multilingual beneficiary profile extractor. Understand natural English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia and code-mixed speech by meaning, including imperfect ASR text. Extract only explicitly stated facts and return valid JSON only. Unknown fields must be null or empty. Schema: {education:{level,status,stream},occupation,skills:[],interests:[],experience:[{domain,duration_months}],location:{state,district},employment_preference,training_willingness,mobility_km,language}. Use CURRENT_QUESTION_TOPIC to interpret short contextual replies. If it is training_willingness, map a semantic yes/willing reply to true and no/unwilling to false. Convert clear durations to months. If the user explicitly says they have no work experience, return experience:[{domain:null,duration_months:0}] so the conversation knows the experience question was answered. Capture dropout/not-completed status without treating it as passed. Never recommend or invent courses, eligibility, schemes, centres or jobs."""

def _next_missing_field(profile: Optional[BeneficiaryProfile]):
    if profile is None: return None
    if not profile.education.level: return "education"
    if not (profile.interests or profile.skills or profile.occupation): return "livelihood_signal"
    if not profile.experience: return "experience"
    if profile.employment_preference is None: return "employment_preference"
    if not (profile.location.district or profile.location.state): return "location"
    if profile.training_willingness is None: return "training_willingness"
    return None

def _compact_profile(profile: Optional[BeneficiaryProfile]):
    if profile is None: return {}
    d=profile.model_dump()
    def compact(v):
        if isinstance(v,dict):
            out={k:compact(x) for k,x in v.items()}
            return {k:x for k,x in out.items() if x not in (None,[],{},"")}
        if isinstance(v,list): return [compact(x) for x in v if compact(x) not in (None,[],{},"")]
        return v
    return compact(d)

def _clean_json(raw: str) -> str:
    s=raw.strip()
    s=re.sub(r'^```(?:json)?\s*','',s,flags=re.I)
    s=re.sub(r'\s*```$','',s)
    return s.strip()


def _redact_secret(value: str, secret: Optional[str]) -> str:
    """Remove an API key from provider/network error text before it reaches logs or UI."""
    out = str(value or "")
    if secret:
        out = out.replace(secret, "<redacted>")
    out = re.sub(r"([?&]key=)[^&\s'\"]+", r"\1<redacted>", out, flags=re.I)
    out = re.sub(r"(GEMINI_API_KEY\s*[=:]\s*)[^\s,;]+", r"\1<redacted>", out, flags=re.I)
    return out


def _provider_connection_error(exc: Exception, secret: Optional[str]) -> RuntimeError:
    safe = _redact_secret(str(exc), secret)
    # Keep a short diagnostic without ever exposing credentials or a full request URL.
    if len(safe) > 300:
        safe = safe[:300] + "..."
    return RuntimeError(f"Gemini connection failed: {safe}")

class OnlineProfileExtractor(ProfileExtractor):
    def __init__(self, provider: Optional[str]=None, model_name: Optional[str]=None, api_key: Optional[str]=None, timeout:int=8, api_caller:Optional[Callable[[str,str],str]]=None):
        self.provider=(provider or os.getenv('LLM_PROVIDER') or 'gemini').lower()
        self.api_key=api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        # Online extraction is a short classification/extraction task, so use the
        # low-latency Flash-Lite model by default. Preserve the user's existing
        # LLM_MODEL only as a fallback; no .env file is inspected or modified here.
        self.model_name=(model_name or os.getenv('SKILLMITRA_ONLINE_MODEL') or 'gemini-3.5-flash-lite').strip()
        self.fallback_model=(os.getenv('LLM_MODEL') or 'gemini-flash-latest').strip()
        self.timeout=timeout
        self.api_caller=api_caller
        self._resolved_model = None

    def _list_models(self):
        if not self.api_key:
            return []
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        try:
            r = requests.get(url, params={"key": self.api_key, "pageSize": 100}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise _provider_connection_error(exc, self.api_key) from None
        if not r.ok:
            return []
        try:
            return r.json().get("models", [])
        except ValueError:
            return []

    def _resolve_model(self, force_refresh: bool = False) -> str:
        """Resolve a fast model without adding a model-list request to normal turns.

        The configured fast model is used directly. Discovery happens only after a
        provider 404, which keeps the common path to a single generateContent call.
        """
        if self._resolved_model and not force_refresh:
            return self._resolved_model
        configured=(self.model_name or '').strip()
        if configured and not force_refresh:
            self._resolved_model=configured
            return configured

        models=self._list_models()
        usable=[]
        for m in models:
            methods=m.get('supportedGenerationMethods') or []
            if 'generateContent' not in methods:
                continue
            name=str(m.get('name','')).replace('models/','')
            low=name.lower()
            if name and 'embedding' not in low and 'image' not in low and 'tts' not in low:
                usable.append(name)
        # Prefer stable Flash-Lite models first for low latency, then Flash.
        for exact in ('gemini-3.5-flash-lite','gemini-3.1-flash-lite'):
            if exact in usable:
                self._resolved_model=exact
                return exact
        lite=[x for x in usable if 'flash-lite' in x.lower()]
        if lite:
            self._resolved_model=sorted(lite)[-1]
            return self._resolved_model
        flash=[x for x in usable if 'flash' in x.lower()]
        if flash:
            self._resolved_model=sorted(flash)[-1]
            return self._resolved_model
        fallback=self.fallback_model or configured or 'gemini-flash-latest'
        self._resolved_model=fallback
        return fallback

    def status(self):
        if self.provider!='gemini':
            return {'ready':False,'provider':self.provider,'detail':'This build enables Gemini REST for online mode.'}
        if not self.api_key:
            return {'ready':False,'provider':'gemini','model':self.model_name or None,'detail':'GEMINI_API_KEY is not set in .env.'}
        try:
            model = self._resolve_model()
            return {'ready':True,'provider':'gemini','model':model,'detail':f'Gemini REST ready with {model}.'}
        except Exception as exc:
            return {'ready':False,'provider':'gemini','model':self.model_name or None,'detail':f"Gemini model discovery failed: {_redact_secret(str(exc), self.api_key)}"}

    def _call_gemini(self,prompt:str,text:str)->str:
        if not self.api_key:
            raise ValueError('GEMINI_API_KEY is not set in .env.')
        model = self._resolve_model()
        body={
            'contents':[{'parts':[{'text':f"{prompt}\n\nUSER INPUT:\n{text}\n\nJSON ONLY:"}]}],
            'generationConfig':{
                'responseMimeType':'application/json',
                'maxOutputTokens':320,
                'thinkingConfig':{'thinkingLevel':'minimal'},
            }
        }
        def do_call(name):
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent"
            try:
                return requests.post(url,params={'key':self.api_key},json=body,timeout=self.timeout)
            except requests.RequestException as exc:
                raise _provider_connection_error(exc, self.api_key) from None
        r=do_call(model)
        # If a configured/cached model was retired, rediscover from the live models endpoint and retry once.
        if r.status_code == 404:
            self._resolved_model = None
            model = self._resolve_model(force_refresh=True)
            r = do_call(model)
        if not r.ok:
            detail=r.text[:600]
            raise RuntimeError(f'Gemini HTTP {r.status_code} using {model}: {detail}')
        data=r.json()
        try:
            return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            raise RuntimeError(f'Gemini returned an unexpected response: {data}') from e

    def _call_provider_api(self,prompt:str,text:str)->str:
        if self.api_caller:
            return self.api_caller(prompt,text)
        if self.provider=='gemini':
            return self._call_gemini(prompt,text)
        raise ValueError(f"Unsupported online provider in this build: '{self.provider}'")

    def extract(self,text:str,current_profile:Optional[BeneficiaryProfile]=None,language_code:Optional[str]=None)->BeneficiaryProfile:
        if not text or not text.strip():
            return current_profile if current_profile else BeneficiaryProfile(language=language_code)
        expected=_next_missing_field(current_profile)
        context=json.dumps(_compact_profile(current_profile),ensure_ascii=False,separators=(",",":"))
        prompt=(f"{SYSTEM_EXTRACTION_PROMPT}\nCURRENT_PROFILE={context}\n"
                f"CURRENT_QUESTION_TOPIC: {expected or 'open_profile_introduction'}\n"
                f"LANG={language_code or 'unknown'}")
        raw=self._call_provider_api(prompt,text)
        try:
            d=json.loads(_clean_json(raw))
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: '{raw}'") from e
        if not isinstance(d,dict):
            raise ValueError('Expected JSON object from online LLM.')
        # Fill omitted container fields so partial JSON stays valid.
        d.setdefault('education', {'level':None,'status':None,'stream':None})
        if isinstance(d.get('education'),dict):
            for k in ('level','status','stream'): d['education'].setdefault(k,None)
        d.setdefault('occupation',None); d.setdefault('skills',[]); d.setdefault('interests',[]); d.setdefault('experience',[])
        d.setdefault('location', {'state':None,'district':None})
        if isinstance(d.get('location'),dict):
            d['location'].setdefault('state',None); d['location'].setdefault('district',None)
        d.setdefault('employment_preference',None); d.setdefault('training_willingness',None); d.setdefault('mobility_km',None); d.setdefault('language',language_code)
        extracted=BeneficiaryProfile.model_validate(d)
        if language_code and not extracted.language: extracted.language=language_code
        return current_profile.merge(extracted) if current_profile else extracted


class HybridOnlineProfileExtractor(OnlineProfileExtractor):
    """Jury-speed online extractor.

    Common education/skill/experience/location replies are handled immediately by
    deterministic local parsing. Gemini Flash-Lite is reserved for genuinely
    unstructured text that the rules did not understand.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fast_extractor = LocalProfileExtractor()
        self.last_mode = "online_fast_rules"

    @staticmethod
    def _signature(profile):
        if profile is None:
            return None
        return (
            profile.education.level, profile.education.status, profile.education.stream,
            profile.occupation, tuple(profile.skills or []), tuple(profile.interests or []),
            tuple((x.domain, x.duration_months) for x in (profile.experience or [])),
            profile.location.state, profile.location.district,
            profile.employment_preference, profile.training_willingness, profile.mobility_km,
        )

    @staticmethod
    def _patch_has_substantive_fact(patch):
        if patch is None:
            return False
        return bool(
            patch.education.level or patch.education.status or patch.education.stream
            or patch.occupation or patch.skills or patch.interests or patch.experience
            or patch.location.state or patch.location.district
            or patch.employment_preference is not None
            or patch.training_willingness is not None
            or patch.mobility_km is not None
        )

    @staticmethod
    def _ambiguous_short_reply(text, current_profile):
        """Replies that contain no resolvable choice should not pay a cloud round-trip."""
        if current_profile is None:
            return False
        expected = _next_missing_field(current_profile)
        t = re.sub(r"[.!?,;:]+", " ", (text or "").lower()).strip()
        if not t or len(t.split()) > 7:
            return False
        generic_yes = bool(re.search(
            r"\b(?:yes|yeah|yep|haan|han|ha|want|interested)\b|"
            r"हाँ|हां|हा|जी|चाहता|चाहती|చాహ|అవును|ஆம்|ಹೌದು|അതെ|हो|হ্যাঁ|હા|ਹਾਂ|ହଁ",
            t,
        ))
        # Employment preference is a 3-way choice.  A bare yes/want cannot resolve it.
        if expected == "employment_preference" and generic_yes:
            return True
        # Education/livelihood/experience/location are not yes/no questions either.
        if expected in {"education", "livelihood_signal", "experience", "location"} and generic_yes:
            return True
        return False

    def extract(self, text, current_profile=None, language_code=None):
        clean=(text or "").strip()
        before=self._signature(current_profile)
        patch=self.fast_extractor.extract_patch(clean, current_profile, language_code)
        if current_profile is None:
            fast=patch
        else:
            fast=current_profile.model_copy(deep=True).merge(patch)
        changed=self._signature(fast) != before
        recognized=self._patch_has_substantive_fact(patch)
        # Stay on the zero-latency path when the sentence was understood even if it
        # merely repeats a fact already in the profile.  This avoids a 5-8 second
        # Gemini call when users repeat "10th class", their city, etc.
        if changed or recognized or self._ambiguous_short_reply(clean, current_profile):
            self.last_mode="online_fast_rules"
            return fast
        self.last_mode=f"online_gemini:{self._resolve_model()}"
        return super().extract(clean, current_profile, language_code)
