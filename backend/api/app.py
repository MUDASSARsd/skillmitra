"""FastAPI transport layer for the SIH livelihood assistant.

The API deliberately keeps recommendation logic deterministic. LLM extraction is
used only by /conversation; /recommend works fully offline from a structured profile.
"""
from pathlib import Path
import sqlite3
import re
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.api.schemas import (
    RecommendRequest, RecommendResponse, ConversationRequest,
    ConversationResponse, HealthResponse, TrainingOptionsResponse, TrainingStatusResponse,
    JobsStatusResponse, JobsSearchResponse, JobDemandResponse, SkillGapRequest,
)
from backend.database.db import DEFAULT_DB_PATH
from backend.recommendation_engine import RecommendationEngine
from backend.nlu.online_extractor import OnlineProfileExtractor, HybridOnlineProfileExtractor
from backend.nlu.local_extractor import LocalProfileExtractor, normalize_contextual_transcript
from backend.nlu.ollama_extractor import HybridOfflineProfileExtractor, OllamaProfileExtractor
from backend.conversation.session import ConversationManager
from backend.stt_local import LocalSTT
from backend.stt_online import OnlineSTT
from backend.tts_local import LocalTTS
from backend.tts_online import OnlineTTS
from backend.mapping.semantic_retriever import SemanticNQRIndex
from backend.training.store import find_training_options, training_data_status, ensure_training_schema
from backend.training.directory import find_directory_centres, directory_status
from backend.training.live_batches import find_live_batches, live_batch_status, ensure_live_batch_schema
from backend.jobs.store import search_jobs, demand_summary, job_evidence, jobs_data_status, ensure_jobs_schema
from backend.skill_gap.engine import SkillGapEngine
from backend.schemes.store import scheme_data_status, list_schemes, import_scheme_snapshot
from backend.schemes.engine import match_schemes
from backend.courses.store import search_courses, courses_for_qualification, course_data_status, ensure_course_schema
from backend.career.engine import OccupationTaxonomy, CareerProgressionEngine
from contextlib import asynccontextmanager
import tempfile
import time
import threading

# Reuse extractors/managers across requests so local models stay warm and Gemini
# model discovery is cached instead of repeated on every beneficiary turn.
_OFFLINE_EXTRACTOR = HybridOfflineProfileExtractor()
_OFFLINE_MANAGER = ConversationManager(_OFFLINE_EXTRACTOR)
_ONLINE_EXTRACTOR = HybridOnlineProfileExtractor()
_ONLINE_MANAGER = ConversationManager(_ONLINE_EXTRACTOR)
_RULE_FALLBACK_MANAGER = ConversationManager(LocalProfileExtractor())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cloud deployment is an Online-AI service and must not probe/load laptop-only
    # speech models. Local mode may warm the project-local ASR in the background.
    runtime = os.getenv("SKILLMITRA_RUNTIME", "local").strip().lower()
    if runtime != "cloud":
        def _warm_local_stt():
            try:
                LocalSTT().warmup()
            except Exception:
                pass
        threading.Thread(target=_warm_local_stt, daemon=True, name="skillmitra-stt-warmup").start()
    yield


app = FastAPI(
    title="PM-AJAY Livelihood & NSQF Recommendation API",
    version="0.17.0",
    description="Profile extraction, counter-questions, local NQR mapping, eligibility and explainable recommendations.",
    lifespan=lifespan,
)

# Development-friendly CORS. Set CORS_ORIGINS in deployment before exposing publicly.
import os
_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False if "*" in _origins else True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR)), name="ui")

@app.get("/app", include_in_schema=False)
def frontend_app():
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})


def _recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine(DEFAULT_DB_PATH)


def _offline_conversation_manager() -> ConversationManager:
    return _OFFLINE_MANAGER


def _conversation_manager() -> ConversationManager:
    return _ONLINE_MANAGER


def _safe_error_detail(exc: Exception) -> str:
    """Defense-in-depth redaction before exception text is returned by the API."""
    msg = str(exc or "")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        msg = msg.replace(key, "<redacted>")
    msg = re.sub(r"([?&]key=)[^&\s'\"]+", r"\1<redacted>", msg, flags=re.I)
    return msg[:800]





@app.get("/jobs/status", response_model=JobsStatusResponse, tags=["jobs"])
def jobs_status():
    """Status of the locally cached NCS/Skill India job snapshot."""
    return JobsStatusResponse(**jobs_data_status(DEFAULT_DB_PATH))


@app.get("/jobs/search", response_model=JobsSearchResponse, tags=["jobs"])
def jobs_search(query: str, state: str | None = None, district: str | None = None, limit: int = 20):
    """Search cached active job openings by role/skills and optional location."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    jobs = search_jobs(query, state=state, district=district, limit=limit, db_path=DEFAULT_DB_PATH)
    return JobsSearchResponse(jobs=[j.model_dump() for j in jobs], count=len(jobs))


@app.get("/jobs/demand", response_model=JobDemandResponse, tags=["jobs"])
def jobs_demand(query: str, state: str | None = None, district: str | None = None):
    """Summarize postings, vacancies and source-reported salary fields for a role/location."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    summary = demand_summary(query, state=state, district=district, db_path=DEFAULT_DB_PATH)
    return JobDemandResponse(summary=summary.model_dump())


@app.get("/jobs/evidence", tags=["jobs"])
def jobs_evidence(query: str, state: str | None = None, district: str | None = None, limit: int = 10):
    """Job openings + demand summary with explicit district -> state -> national fallback."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    ev = job_evidence(query, state=state, district=district, limit=limit, db_path=DEFAULT_DB_PATH)
    return {
        "query": query,
        "scope": ev["scope"],
        "location": {"state": ev["state"], "district": ev["district"]},
        "fallback_used": ev["fallback_used"],
        "jobs": [j.model_dump() for j in ev["jobs"]],
        "job_demand": ev["summary"].model_dump(),
        "live_refresh_recommended": True,
    }


@app.post("/skill-gap/analyze", tags=["skill-gap"])
def skill_gap_analyze(req: SkillGapRequest):
    """Compare beneficiary-stated skills with skill signals grounded in the stored NQR description.

    Missing profile evidence is not treated as proof that the beneficiary lacks a skill.
    Cached job tags are returned separately as time-sensitive market signals.
    """
    try:
        result = SkillGapEngine(DEFAULT_DB_PATH).analyze(
            req.profile, req.qualification_code,
            include_market=req.include_market, market_limit=req.market_limit,
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc




@app.get("/courses/status", tags=["courses", "training"])
def courses_status():
    """Status of the cached Skill India course-catalogue snapshot."""
    return course_data_status(DEFAULT_DB_PATH)


@app.get("/courses/search", tags=["courses", "training"])
def courses_search(query: str, language: str | None = None, limit: int = 20):
    """Search cached Skill India courses by title/occupation/domain.

    Catalogue availability is not treated as proof of a current local seat or batch.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    matches = search_courses(query, language=language, limit=limit, db_path=DEFAULT_DB_PATH)
    return {
        "query": query,
        "matches": [x.model_dump() for x in matches],
        "count": len(matches),
        "data_mode": "cached_skill_india_catalogue",
        "live_batch_confirmation_required": True,
        "official_course_url": "https://courses.skillindiadigital.gov.in/courses/",
    }


@app.get("/courses/for-qualification", tags=["courses", "training"])
def courses_for_qualification_api(qualification_code: str, limit: int = 10):
    """Find Skill India catalogue courses related to an NQR recommendation."""
    matches = courses_for_qualification(qualification_code, limit=limit, db_path=DEFAULT_DB_PATH)
    return {
        "qualification_code": qualification_code,
        "matches": [x.model_dump() for x in matches],
        "count": len(matches),
        "data_mode": "cached_skill_india_catalogue",
        "match_note": "Exact QP-code evidence is preferred; title/occupation matching is used when Skill India and NQR code schemes differ.",
        "live_batch_confirmation_required": True,
    }

@app.get("/training/status", response_model=TrainingStatusResponse, tags=["training"])
def training_status():
    """Status of the locally cached official training-centre/course data."""
    return TrainingStatusResponse(**training_data_status(DEFAULT_DB_PATH))


@app.get("/training/options", response_model=TrainingOptionsResponse, tags=["training"])
def training_options(qualification_code: str | None = None, job_role: str | None = None,
                     state: str | None = None, district: str | None = None, limit: int = 20):
    """Find cached training options by qualification/job role and location.

    Cached availability is never represented as live truth; the response always
    requires live confirmation on Skill India Digital before enrolment.
    """
    if not qualification_code and not job_role:
        raise HTTPException(status_code=400, detail="Provide qualification_code or job_role.")
    options = find_training_options(qualification_code=qualification_code, job_role=job_role,
                                    state=state, district=district, limit=limit, db_path=DEFAULT_DB_PATH)
    return TrainingOptionsResponse(options=[x.model_dump() for x in options], count=len(options))


@app.get("/training/centres", tags=["training"])
def training_centres_directory(state: str | None = None, district: str | None = None,
                               query: str | None = None, limit: int = 25):
    """Search verified official directory centres without pretending a live batch exists.

    These results are directory/history evidence. Qualification compatibility and
    current enrolment availability remain unknown unless an explicit offering exists.
    """
    centres = find_directory_centres(state=state, district=district, query=query,
                                     limit=limit, db_path=DEFAULT_DB_PATH)
    # If an exact district has no verified rows, fall back to state rather than returning
    # unrelated national centres. The scope is explicit in the response.
    scope = "DISTRICT" if district else ("STATE" if state else "UNFILTERED")
    if not centres and district and state:
        centres = find_directory_centres(state=state, limit=limit, db_path=DEFAULT_DB_PATH)
        scope = "STATE_FALLBACK"
    return {
        "centres": centres,
        "count": len(centres),
        "location_scope": scope,
        "verification": "OFFICIAL_DIRECTORY",
        "batch_status": "UNKNOWN_UNLESS_EXPLICIT_OFFERING_EXISTS",
        "warning": "Historical/report Batch Count is not current seat or batch availability.",
    }


@app.get("/training/directory-status", tags=["training"])
def training_directory_status():
    return directory_status(DEFAULT_DB_PATH)


@app.get("/training/batch-status", tags=["training"])
def training_batch_status():
    """Status of imported live/captured official batch evidence."""
    return live_batch_status(DEFAULT_DB_PATH)


@app.get("/training/live-batches", tags=["training"])
def training_live_batches(qualification_code: str | None = None, job_role: str | None = None,
                          state: str | None = None, district: str | None = None,
                          active_only: bool = True, limit: int = 20):
    """Search only explicit batch observations imported from an official live response.

    Directory/history Batch Count is intentionally excluded from this endpoint.
    """
    if not qualification_code and not job_role:
        raise HTTPException(status_code=400, detail="Provide qualification_code or job_role.")
    rows = find_live_batches(qualification_code=qualification_code, job_role=job_role,
                             state=state, district=district, active_only=active_only,
                             limit=limit, db_path=DEFAULT_DB_PATH)
    scope = "DISTRICT" if district else ("STATE" if state else "UNFILTERED")
    if not rows and district and state:
        rows = find_live_batches(qualification_code=qualification_code, job_role=job_role,
                                 state=state, active_only=active_only, limit=limit,
                                 db_path=DEFAULT_DB_PATH)
        scope = "STATE_FALLBACK"
    return {
        "batches": rows,
        "count": len(rows),
        "location_scope": scope,
        "evidence_rule": "Only explicit official batch observations are returned; directory batch counts are never treated as live availability.",
        "seat_truth": "UNKNOWN unless seats_available is explicitly provided by the source.",
    }


@app.get("/training/live-handoff", tags=["training"])
def training_live_handoff(job_role: str | None = None):
    """Return the official learner destination for current batch confirmation."""
    return {
        "official_url": "https://www.skillindiadigital.gov.in/home",
        "job_role": job_role,
        "instruction": "Login/eKYC on Skill India Digital, open Skill Courses/PMKVY, search this job role, and verify Batch ID, Location, Training Centre, Training Partner, start date and timing before applying.",
        "live_confirmation_required": True,
    }


@app.get("/taxonomy/status", tags=["career", "taxonomy"])
def taxonomy_status():
    return OccupationTaxonomy(DEFAULT_DB_PATH).status()


@app.get("/taxonomy/search", tags=["career", "taxonomy"])
def taxonomy_search(query: str, sector: str | None = None, limit: int = 20):
    """Search an NQR-derived occupation family/alias view.

    Aliases are retrieval aids derived from official qualification titles and proposed
    occupation labels; they are not a separate government occupation standard.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    rows = OccupationTaxonomy(DEFAULT_DB_PATH).search(query, sector=sector, limit=limit)
    return {"query": query, "matches": rows, "count": len(rows), "mode": "derived_from_local_nqr"}


@app.get("/career/progression", tags=["career"])
def career_progression(qualification_code: str, related_limit: int = 8):
    """Return official NQR progression text plus clearly-labelled related higher NSQF options."""
    try:
        return CareerProgressionEngine(DEFAULT_DB_PATH).analyze(qualification_code, related_limit=related_limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/schemes/status", tags=["schemes"])
def schemes_status():
    return scheme_data_status(DEFAULT_DB_PATH)


@app.get("/schemes/list", tags=["schemes"])
def schemes_list():
    """List the curated official scheme snapshot and provenance."""
    return {"schemes": list_schemes(DEFAULT_DB_PATH), **scheme_data_status(DEFAULT_DB_PATH)}


@app.post("/schemes/match", tags=["schemes"])
def schemes_match(profile: dict):
    """Conservative scheme relevance/eligibility screening from a beneficiary profile.

    The result is decision support only. INFO_NEEDED/POSSIBLE_MATCH are deliberately
    used when the profile lacks a condition required by the official scheme.
    """
    from backend.models.beneficiary import BeneficiaryProfile
    p = BeneficiaryProfile.model_validate(profile)
    return {
        "matches": match_schemes(p, DEFAULT_DB_PATH),
        "scheme_data": scheme_data_status(DEFAULT_DB_PATH),
        "rule": "No scheme is presented as guaranteed eligibility; official application channels make the final determination.",
    }


@app.get("/", tags=["system"])
def root():
    return {
        "name": "PM-AJAY Livelihood & NSQF Recommendation API",
        "status": "ok",
        "docs": "/docs",
        "offline_recommendation": "/recommend",
        "skill_gap": "/skill-gap/analyze",
        "courses": "/courses/search",
        "schemes": "/schemes/match",
        "online_conversation": "/conversation",
        "frontend": "/app",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    db = Path(DEFAULT_DB_PATH)
    if not db.exists():
        return HealthResponse(status="degraded", database_ready=False,
                              qualification_count=0, eligibility_route_count=0)
    try:
        with sqlite3.connect(str(db)) as conn:
            q_count = conn.execute("SELECT COUNT(*) FROM qualifications").fetchone()[0]
            e_count = conn.execute("SELECT COUNT(*) FROM eligibility_routes").fetchone()[0]
        return HealthResponse(status="ok", database_ready=True,
                              qualification_count=q_count, eligibility_route_count=e_count)
    except sqlite3.Error:
        return HealthResponse(status="degraded", database_ready=False,
                              qualification_count=0, eligibility_route_count=0)



@app.get("/stt/offline/status", tags=["speech"])
def offline_stt_status():
    return LocalSTT().status().as_dict()


@app.get("/nlu/offline/status", tags=["nlu"])
def offline_nlu_status():
    """Report offline NLU readiness without making Ollama a hard dependency."""
    ollama = OllamaProfileExtractor().status()
    return {
        "ready": True,
        "engine": "deterministic-local+optional-ollama",
        "detail": (
            "Deterministic multilingual offline profile extraction is ready. "
            "Ollama is optional and is used only to enrich unusually complex free-form descriptions."
        ),
        "ollama": ollama,
    }


@app.get("/nlu/online/status", tags=["nlu"])
def online_nlu_status():
    """Reports whether Gemini online extraction has an API key configured."""
    return OnlineProfileExtractor().status()


@app.get("/mapping/semantic/status", tags=["recommendation"])
def semantic_mapping_status():
    """Reports whether the local multilingual NQR vector index is ready."""
    return SemanticNQRIndex().status().as_dict()


@app.get("/system/readiness", tags=["system"])
def system_readiness():
    """One-screen runtime readiness summary for demos and troubleshooting.

    This endpoint performs only local/status checks. It does not call Gemini or refresh
    any external job/course/training source.
    """
    stt = LocalSTT().status().as_dict()
    tts = LocalTTS().status().as_dict()
    semantic = SemanticNQRIndex().status().as_dict()
    online = OnlineProfileExtractor().status()
    jobs = jobs_data_status(DEFAULT_DB_PATH)
    courses = course_data_status(DEFAULT_DB_PATH)
    training = training_data_status(DEFAULT_DB_PATH)
    live_batches = live_batch_status(DEFAULT_DB_PATH)
    schemes = scheme_data_status(DEFAULT_DB_PATH)
    # Offline text conversation + deterministic NQR mapping is the core.
    # Microphone/TTS are optional capabilities and must not make the whole system
    # look "partially ready" when the recommendation engine itself is healthy.
    offline_core_ready = bool(semantic.get("ready") and Path(DEFAULT_DB_PATH).exists())
    offline_voice_ready = bool(stt.get("ready") and tts.get("ready"))
    return {
        "offline_core_ready": offline_core_ready,
        "offline_voice_ready": offline_voice_ready,
        "speech_to_text": stt,
        "text_to_speech": tts,
        "semantic_mapping": semantic,
        "online_nlu": online,
        "jobs_cache": jobs,
        "courses_cache": courses,
        "training_cache": training,
        "live_batch_cache": live_batches,
        "schemes_cache": schemes,
        "notes": [
            "Offline microphone and speech output are optional capabilities; text conversation and local NQR mapping remain usable without them.",
            "Training-centre directory and live batch evidence are tracked separately; historical batch counts are never exposed as current availability.",
            "Online NLU readiness only reports configuration/status and does not affect offline mode.",
        ],
    }


@app.post("/stt/offline", tags=["speech"])
async def offline_stt(audio: UploadFile = File(...), language: str = Form("auto"), expected_field: str = Form("")):
    """Transcribe microphone WAV locally using the selected offline ASR engine. No cloud/API call."""
    if not (audio.filename or "").lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Upload a mono 16-bit PCM WAV file.")
    stt = LocalSTT()
    status = stt.status()
    if not status.ready:
        raise HTTPException(status_code=503, detail=status.detail)
    data = await audio.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file is too large.")
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(data); tmp_name = tmp.name
        text, engine = stt.transcribe(Path(tmp_name), language)
        normalized = normalize_contextual_transcript(text, expected_field or None, language)
        return {
            "text": normalized,
            "raw_text": text if normalized != text else None,
            "normalized": normalized != text,
            "engine": engine,
            "language": language,
            "offline": True,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
            Path(tmp_name + ".txt").unlink(missing_ok=True)



@app.get("/stt/online/status", tags=["speech"])
def online_stt_status():
    """Report whether Online AI microphone transcription is configured."""
    return OnlineSTT(fallback_model=_ONLINE_EXTRACTOR.model_name or None).status().as_dict()


@app.post("/stt/online", tags=["speech"])
async def online_stt(audio: UploadFile = File(...), language: str = Form("auto")):
    """Transcribe a short microphone WAV with multilingual online ASR.

    This route is intentionally separate from profile extraction so the UI can show
    the transcript for review before sending it into the recommendation flow.
    """
    if not (audio.filename or "").lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Upload a mono 16-bit PCM WAV file.")
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Audio recording is empty.")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file is too large.")

    fallback_model = _ONLINE_EXTRACTOR._resolved_model or _ONLINE_EXTRACTOR.model_name or None
    stt = OnlineSTT(api_key=_ONLINE_EXTRACTOR.api_key, fallback_model=fallback_model)
    try:
        text, engine = stt.transcribe(data, language=language, mime_type="audio/wav")
        return {"text": text, "engine": engine, "language": language, "offline": False}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_error_detail(exc)) from exc


@app.get("/tts/offline/status", tags=["speech"])
def offline_tts_status():
    return LocalTTS().status().as_dict()


@app.get("/tts/online/status", tags=["speech"])
def online_tts_status():
    return OnlineTTS().status().as_dict()


@app.post("/tts/online", tags=["speech"])
async def online_tts(payload: dict):
    text = str(payload.get("text", "")).strip()
    language = str(payload.get("language", "en"))
    if len(text) > 1200:
        raise HTTPException(status_code=413, detail="Text is too long for online TTS.")
    try:
        path = await OnlineTTS().synthesize(text, language)
        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return Response(content=data, media_type="audio/mpeg")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_safe_error_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Online speech service unavailable: {_safe_error_detail(exc)}") from exc




@app.post("/tts/offline/play-local", tags=["speech"])
def offline_tts_play_local(payload: dict):
    """Play Offline TTS on the same Windows laptop that runs FastAPI.

    This route exists for the local/offline jury runtime and bypasses browser
    autoplay restrictions.  Non-Windows deployments return 503 and the frontend
    falls back to the ordinary WAV endpoint.
    """
    text = str(payload.get("text", "")).strip()
    language = str(payload.get("language", "en"))
    if len(text) > 1200:
        raise HTTPException(status_code=413, detail="Text is too long for local TTS.")
    try:
        LocalTTS().play_on_device_async(text, language)
        return {"ok": True, "language": language, "playback": "windows-local-speaker"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/tts/offline", tags=["speech"])
def offline_tts(payload: dict):
    text = str(payload.get("text", "")).strip()
    language = str(payload.get("language", "te"))
    if len(text) > 1200:
        raise HTTPException(status_code=413, detail="Text is too long for local TTS.")
    try:
        path = LocalTTS().synthesize(text, language)
        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return Response(content=data, media_type="audio/wav")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.post("/recommend", response_model=RecommendResponse, tags=["recommendation"])
def recommend(req: RecommendRequest):
    """Offline-capable deterministic NQR recommendation from an existing profile."""
    try:
        recs = _recommendation_engine().recommend(
            req.profile, top_k=req.top_k, candidate_limit=req.candidate_limit
        )
        return RecommendResponse(recommendations=recs, count=len(recs))
    except (ValueError, sqlite3.Error) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.post("/recommend/with-training", tags=["recommendation", "training"])
def recommend_with_training(req: RecommendRequest):
    """Recommend NQR qualifications and enrich each result with cached local training options.

    Training availability is cache metadata, not a promise of a live seat. Current
    batches must be confirmed on Skill India Digital.
    """
    recs = _recommendation_engine().recommend(req.profile, top_k=req.top_k, candidate_limit=req.candidate_limit)
    state = req.profile.location.state
    district = req.profile.location.district
    enriched = []
    for rec in recs:
        code = rec.qualification.code
        options = []
        if code:
            options = find_training_options(qualification_code=code, state=state, district=district, limit=5, db_path=DEFAULT_DB_PATH)
            if not options and district and state:
                options = find_training_options(qualification_code=code, state=state, limit=5, db_path=DEFAULT_DB_PATH)
        enriched.append({
            "recommendation": rec.model_dump(),
            "training_options": [x.model_dump() for x in options],
            "training_option_count": len(options),
            "live_confirmation_required": True,
            "official_live_url": "https://www.skillindiadigital.gov.in/home",
        })
    directory_centres = find_directory_centres(state=state, district=district, limit=10, db_path=DEFAULT_DB_PATH)
    directory_scope = "DISTRICT" if district else ("STATE" if state else "UNFILTERED")
    if not directory_centres and district and state:
        directory_centres = find_directory_centres(state=state, limit=10, db_path=DEFAULT_DB_PATH)
        directory_scope = "STATE_FALLBACK"
    return {
        "results": enriched,
        "count": len(enriched),
        "location": {"state": state, "district": district},
        "training_data": training_data_status(DEFAULT_DB_PATH),
        "live_batch_data": live_batch_status(DEFAULT_DB_PATH),
        "verified_directory_centres": directory_centres,
        "verified_directory_scope": directory_scope,
        "directory_batch_warning": "Directory presence is verified; current QP/batch/seat availability is unknown unless an explicit offering is present.",
    }


@app.post("/recommend/with-opportunities", tags=["recommendation", "training", "jobs"])
def recommend_with_opportunities(req: RecommendRequest):
    """Recommend qualifications, then enrich with cached training options and job-demand evidence.

    Job evidence does not change the core qualification relevance score. It is shown
    as a separate, time-sensitive decision-support layer.
    """
    recs = _recommendation_engine().recommend(req.profile, top_k=req.top_k, candidate_limit=req.candidate_limit)
    state = req.profile.location.state
    district = req.profile.location.district
    results = []
    for rec in recs:
        code = rec.qualification.code
        title = rec.qualification.title
        occupation = rec.qualification.proposed_occupation
        training = []
        course_matches = []
        live_batches = []
        if code:
            training = find_training_options(qualification_code=code, state=state, district=district, limit=5, db_path=DEFAULT_DB_PATH)
            if not training and state:
                training = find_training_options(qualification_code=code, state=state, limit=5, db_path=DEFAULT_DB_PATH)
            course_matches = courses_for_qualification(code, limit=5, db_path=DEFAULT_DB_PATH)
            live_batches = find_live_batches(qualification_code=code, state=state, district=district, limit=5, db_path=DEFAULT_DB_PATH)
            if not live_batches and state:
                live_batches = find_live_batches(qualification_code=code, state=state, limit=5, db_path=DEFAULT_DB_PATH)
            # Some official course/batch feeds omit or use a different QP-code scheme.
            # Only then fall back to strict multi-token role/title matching.
            if not live_batches and (title or occupation):
                live_batches = find_live_batches(job_role=(title or occupation), state=state, district=district, limit=5, db_path=DEFAULT_DB_PATH)
                if not live_batches and state:
                    live_batches = find_live_batches(job_role=(title or occupation), state=state, limit=5, db_path=DEFAULT_DB_PATH)
        # Qualification titles are generally more specific than raw occupation labels such as "Technician".
        # Fall back to proposed occupation only when the title finds no cached evidence.
        primary_query = (title or "").strip()
        fallback_query = (occupation or "").strip()
        job_query = primary_query or fallback_query
        evidence = job_evidence(job_query, state=state, district=district, limit=5, db_path=DEFAULT_DB_PATH) if job_query else None
        # If an over-specific qualification title has no evidence, retry the broader occupation label.
        if evidence and not evidence["jobs"] and fallback_query and fallback_query.casefold() != job_query.casefold():
            job_query = fallback_query
            evidence = job_evidence(job_query, state=state, district=district, limit=5, db_path=DEFAULT_DB_PATH)
        jobs = evidence["jobs"] if evidence else []
        summary = evidence["summary"] if evidence else None
        skill_gap = None
        if code:
            try:
                skill_gap = SkillGapEngine(DEFAULT_DB_PATH).analyze(req.profile, code, include_market=True, market_limit=5)
            except ValueError:
                skill_gap = None
        career_progression = None
        if code:
            try:
                career_progression = CareerProgressionEngine(DEFAULT_DB_PATH).analyze(code, related_limit=5)
            except ValueError:
                career_progression = None
        results.append({
            "recommendation": rec.model_dump(),
            "career_progression": career_progression,
            "training_options": [x.model_dump() for x in training],
            "skill_india_courses": [x.model_dump() for x in course_matches],
            "skill_india_course_count": len(course_matches),
            "verified_live_batches": live_batches,
            "verified_live_batch_count": len(live_batches),
            "jobs": [x.model_dump() for x in jobs],
            "job_demand": summary.model_dump() if summary else None,
            "skill_gap": skill_gap.model_dump() if skill_gap else None,
            "job_query": job_query,
            "job_location_scope": evidence["scope"] if evidence else "none",
            "job_location_fallback_used": evidence["fallback_used"] if evidence else False,
            "live_job_refresh_recommended": True,
            "training_live_confirmation_required": True,
            "course_catalogue_live_batch_confirmation_required": True,
            "official_course_url": "https://courses.skillindiadigital.gov.in/courses/",
            "official_training_directory_url": "https://www.nsdcindia.org/skillcentres",
        })
    directory_centres = find_directory_centres(state=state, district=district, limit=10, db_path=DEFAULT_DB_PATH)
    directory_scope = "DISTRICT" if district else ("STATE" if state else "UNFILTERED")
    if not directory_centres and district and state:
        directory_centres = find_directory_centres(state=state, limit=10, db_path=DEFAULT_DB_PATH)
        directory_scope = "STATE_FALLBACK"
    scheme_matches = match_schemes(req.profile, DEFAULT_DB_PATH)
    return {
        "results": results,
        "count": len(results),
        "location": {"state": state, "district": district},
        "scheme_matches": scheme_matches,
        "schemes_data": scheme_data_status(DEFAULT_DB_PATH),
        "training_data": training_data_status(DEFAULT_DB_PATH),
        "live_batch_data": live_batch_status(DEFAULT_DB_PATH),
        "verified_directory_centres": directory_centres,
        "verified_directory_scope": directory_scope,
        "directory_batch_warning": "Directory presence is verified; current QP/batch/seat availability is unknown unless an explicit offering is present.",
        "jobs_data": jobs_data_status(DEFAULT_DB_PATH),
        "notes": [
            "Job demand is based on cached active postings and is not a forecast or guarantee of employment.",
            "Salary values are summarized from source-provided fields; source anomalies are preserved rather than silently corrected.",
            "Current training batches are shown only when an explicit official batch observation has been imported; otherwise Skill India Digital confirmation is required.",
            "PwD/Divyangjan-specific qualifications are suppressed unless disability context is explicitly present in the beneficiary profile."
        ],
    }


@app.post("/conversation/offline", response_model=ConversationResponse, tags=["conversation"])
def offline_conversation(req: ConversationRequest):
    """No-cloud local extraction + counter-questions + local recommendations.

    Optional Ollama enrichment is never allowed to break the beneficiary flow. Any
    malformed/partial local-LLM JSON silently falls back to deterministic rules.
    """
    t0=time.perf_counter()
    extraction_mode="offline_rules"
    try:
        turn = _offline_conversation_manager().process(
            req.text, current_profile=req.current_profile, language_code=req.language_code
        )
        used = _OFFLINE_EXTRACTOR.last_model_used or "rules-fastpath"
        extraction_mode = f"offline_{used}"
    except Exception:
        turn = _RULE_FALLBACK_MANAGER.process(
            req.text, current_profile=req.current_profile, language_code=req.language_code
        )
        extraction_mode = "offline_rules_fallback"

    t1=time.perf_counter()
    recs = []
    try:
        if req.include_recommendations and turn.completeness.ready_for_mapping:
            recs = _recommendation_engine().recommend(turn.profile, top_k=req.top_k)
    except (ValueError, sqlite3.Error):
        recs = []
        extraction_mode += ":recommendation_fallback"
    t2=time.perf_counter()
    return ConversationResponse(
        profile=turn.profile,
        ready_for_mapping=turn.completeness.ready_for_mapping,
        missing_critical=turn.completeness.missing_critical,
        missing_enrichment=turn.completeness.missing_enrichment,
        next_question=turn.next_question,
        recommendations=recs,
        extraction_mode=extraction_mode,
        timings_ms={"nlu":round((t1-t0)*1000,1),"recommendation":round((t2-t1)*1000,1),"total":round((t2-t0)*1000,1)},
    )

@app.post("/conversation", response_model=ConversationResponse, tags=["conversation"])
def conversation(req: ConversationRequest):
    """Gemini-first extraction with a local deterministic fallback.

    The beneficiary flow should not stop just because the cloud provider is slow,
    unreachable, rate-limited, or temporarily unavailable.
    """
    t0=time.perf_counter()
    extraction_mode="online_fast"
    try:
        turn = _conversation_manager().process(
            req.text, current_profile=req.current_profile, language_code=req.language_code
        )
        extraction_mode = getattr(_ONLINE_EXTRACTOR, "last_mode", "online_fast")
    except Exception:
        # Do not expose provider/network stack traces to beneficiaries or judges.
        # The fallback is intentionally deterministic and local.
        extraction_mode="online_fallback_local_rules"
        turn = _RULE_FALLBACK_MANAGER.process(
            req.text, current_profile=req.current_profile, language_code=req.language_code
        )

    t1=time.perf_counter()
    recs = []
    if req.include_recommendations and turn.completeness.ready_for_mapping:
        recs = _recommendation_engine().recommend(turn.profile, top_k=req.top_k)
    t2=time.perf_counter()

    return ConversationResponse(
        profile=turn.profile,
        ready_for_mapping=turn.completeness.ready_for_mapping,
        missing_critical=turn.completeness.missing_critical,
        missing_enrichment=turn.completeness.missing_enrichment,
        next_question=turn.next_question,
        recommendations=recs,
        extraction_mode=extraction_mode,
        timings_ms={"nlu":round((t1-t0)*1000,1),"recommendation":round((t2-t1)*1000,1),"total":round((t2-t0)*1000,1)},
    )
