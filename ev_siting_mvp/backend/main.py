"""
HK EV Charging Station Site Selection - FastAPI Backend
Run with:  uvicorn main:app --reload --port 8000
"""

import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env from repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

GOOGLE_STREETVIEW_KEY = os.getenv("GOOGLEMAP_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HK EV Charging Site Selection API",
    version="2.0.0",
    description="Spatial suitability modelling for EV charging station placement in Hong Kong.",
)

# CORS – allow the local frontend (and any origin for dev convenience)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Vite build at /app (production)
_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"
)
if os.path.exists(_FRONTEND_DIST):
    app.mount("/app", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")


# ─── Request / Response Models ────────────────────────────────────────────────

class SitingRequest(BaseModel):
    weights: dict  # keys: population, poi, road_accessibility, ev_competition, slope, landuse
    num_sites: int = 5


class PreprocessFactorRequest(BaseModel):
    source: str = ""   # optional override filename in raw_data/


# ─── Preprocessing state ──────────────────────────────────────────────────────

_preprocessing_running: bool = False
_factor_preprocessing: dict[str, bool] = {}


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["util"])
def health_check():
    return {"status": "ok"}


@app.get("/api/status", tags=["util"])
def get_status():
    """Return the preprocessing status for every factor raster."""
    try:
        from arcpy_engine import get_preprocessing_status
        return get_preprocessing_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/raw-sources", tags=["data"])
def get_raw_sources():
    """List available raw data files grouped by type."""
    try:
        from arcpy_engine import list_raw_sources
        return list_raw_sources()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/preprocess", tags=["preprocessing"])
def trigger_preprocess(background_tasks: BackgroundTasks):
    """Start the full preprocessing pipeline in the background."""
    global _preprocessing_running
    if _preprocessing_running:
        return {"status": "running", "message": "Preprocessing is already in progress."}

    def _run():
        global _preprocessing_running
        _preprocessing_running = True
        try:
            from arcpy_engine import preprocess_all
            preprocess_all()
            logger.info("Preprocessing finished successfully.")
        except Exception as exc:
            logger.error("Preprocessing failed: %s", exc, exc_info=True)
        finally:
            _preprocessing_running = False

    background_tasks.add_task(_run)
    return {
        "status": "started",
        "message": "Preprocessing started in the background. Poll GET /api/status to track progress.",
    }


@app.post("/api/preprocess/{factor_key}", tags=["preprocessing"])
def trigger_preprocess_factor(
    factor_key: str,
    body: PreprocessFactorRequest,
    background_tasks: BackgroundTasks,
):
    """Preprocess a single factor in the background."""
    from arcpy_engine import PREPROCESS_FUNCS

    if factor_key not in PREPROCESS_FUNCS:
        raise HTTPException(status_code=404, detail=f"Unknown factor: {factor_key}")
    if _factor_preprocessing.get(factor_key):
        return {"status": "running", "message": f"{factor_key} preprocessing already in progress."}

    def _run():
        _factor_preprocessing[factor_key] = True
        try:
            PREPROCESS_FUNCS[factor_key](source=body.source)
            logger.info("Factor preprocessing finished: %s", factor_key)
        except Exception as exc:
            logger.error("Factor preprocessing failed (%s): %s", factor_key, exc, exc_info=True)
        finally:
            _factor_preprocessing[factor_key] = False

    background_tasks.add_task(_run)
    return {"status": "started", "factor": factor_key}


@app.post("/api/siting", tags=["analysis"])
def compute_siting(request: SitingRequest):
    """Run the weighted suitability model and return top N candidate sites."""
    if request.num_sites < 1 or request.num_sites > 50:
        raise HTTPException(status_code=422, detail="num_sites must be between 1 and 50.")

    try:
        from arcpy_engine import run_suitability_model
        result = run_suitability_model(request.weights, request.num_sites)
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Siting analysis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Results history ──────────────────────────────────────────────────────────

@app.get("/api/results", tags=["results"])
def get_results():
    """List all saved result files."""
    from arcpy_engine import list_saved_results
    return list_saved_results()


@app.get("/api/results/{filename}", tags=["results"])
def get_result_file(filename: str):
    """Load a specific saved result GeoJSON."""
    from arcpy_engine import load_result_file
    try:
        return load_result_file(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Result not found: {filename}")


# ─── Street View proxy ───────────────────────────────────────────────────────

@app.get("/api/streetview", tags=["util"])
async def streetview_proxy(
    lat: float = Query(...),
    lng: float = Query(...),
    size: str = Query("400x300"),
    heading: int = Query(0),
):
    """Proxy Google Street View Static API to hide the API key from the client."""
    if not GOOGLE_STREETVIEW_KEY:
        raise HTTPException(status_code=503, detail="Google Street View API key not configured.")
    url = "https://maps.googleapis.com/maps/api/streetview"
    params = {
        "location": f"{lat},{lng}",
        "size": size,
        "heading": str(heading),
        "key": GOOGLE_STREETVIEW_KEY,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Street View API request failed.")
    from fastapi.responses import Response
    return Response(
        content=resp.content,
        media_type=resp.headers.get("Content-Type", "image/jpeg"),
    )
