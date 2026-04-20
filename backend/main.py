"""
HK EV Charging Station Site Selection – FastAPI Backend (root/backend version)
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
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT   = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

GOOGLE_STREETVIEW_KEY = os.getenv("GOOGLEMAP_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HK EV Charging Site Selection API",
    version="3.0.0",
    description="Spatial suitability modelling for EV charging station placement in Hong Kong.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Vite build at /app (production)
_FRONTEND_DIST = os.path.join(_REPO_ROOT, "frontend", "dist")
if os.path.exists(_FRONTEND_DIST):
    app.mount("/app", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")


# ─── Request / Response Models ────────────────────────────────────────────────

class SitingRequest(BaseModel):
    weights: dict       # keys: population, poi, road_accessibility, ev_competition, slope, landuse
    num_sites: int = 5
    study_area: list = []   # list of NAME_EN district strings; empty = all HK


class PreprocessFactorRequest(BaseModel):
    source: str = ""    # optional override filename in raw_data/


# ─── Preprocessing state ──────────────────────────────────────────────────────

_preprocessing_running: bool = False
_factor_preprocessing: dict = {}


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["util"])
def health_check():
    return {"status": "ok"}


@app.get("/api/status", tags=["util"])
def get_status():
    """Return preprocessing status for every factor raster, plus any currently running factors."""
    try:
        from arcpy_engine import get_preprocessing_status
        data = get_preprocessing_status()
        # Append which factors are currently being preprocessed in background
        data["running_factors"] = [k for k, v in _factor_preprocessing.items() if v]
        data["preprocess_running"] = _preprocessing_running
        return data
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


# ─── District endpoints ───────────────────────────────────────────────────────

@app.get("/api/districts", tags=["districts"])
def get_districts():
    """Return sorted list of 18-district English names."""
    try:
        from arcpy_engine import list_districts
        return list_districts()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/districts/geojson", tags=["districts"])
def get_districts_geojson():
    """Return WGS84 GeoJSON FeatureCollection for all 18 districts (boundary outlines)."""
    try:
        from arcpy_engine import get_districts_geojson
        return get_districts_geojson()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Preprocessing ────────────────────────────────────────────────────────────

@app.post("/api/preprocess", tags=["preprocessing"])
def trigger_preprocess(background_tasks: BackgroundTasks):
    """Start the full preprocessing pipeline in the background."""
    global _preprocessing_running
    if _preprocessing_running:
        return {"status": "running", "message": "Preprocessing already in progress."}

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
        "message": "Preprocessing started. Poll GET /api/status to track progress.",
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


# ─── Siting analysis ──────────────────────────────────────────────────────────

@app.post("/api/siting", tags=["analysis"])
def compute_siting(request: SitingRequest):
    """Run the weighted suitability model and return top N candidate sites."""
    if request.num_sites < 1 or request.num_sites > 50:
        raise HTTPException(status_code=422, detail="num_sites must be between 1 and 50.")
    try:
        from arcpy_engine import run_suitability_model
        result = run_suitability_model(
            request.weights,
            request.num_sites,
            study_area=request.study_area or None,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Siting analysis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Layer export ─────────────────────────────────────────────────────────────

@app.get("/api/layer/raster/{name}", tags=["layers"])
def get_raster_layer(name: str):
    """
    Export a preprocessed raster as a 50 m colourised PNG with WGS84 bounds.
    Valid names: pop_density, poi_heat, road_dist, ev_dist, slope_score,
                 landuse_score, final_score.
    """
    try:
        from arcpy_engine import export_raster_overlay
        return export_raster_overlay(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Raster export error (%s): %s", name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/layer/vector/{name}", tags=["layers"])
def get_vector_layer(name: str):
    """
    Export a vector layer as WGS84 GeoJSON.
    Valid names: ev_charger, population, districts, poi_sample.
    """
    try:
        from arcpy_engine import export_vector_layer
        return export_vector_layer(name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Vector export error (%s): %s", name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Results history ──────────────────────────────────────────────────────────

@app.get("/api/results", tags=["results"])
def get_results():
    from arcpy_engine import list_saved_results
    return list_saved_results()


@app.get("/api/results/{filename}", tags=["results"])
def get_result_file(filename: str):
    from arcpy_engine import load_result_file
    try:
        return load_result_file(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Result not found: {filename}")


# ─── Street View proxy ────────────────────────────────────────────────────────

@app.get("/api/streetview", tags=["util"])
async def streetview_proxy(
    lat: float = Query(...),
    lng: float = Query(...),
    size: str = Query("400x300"),
    heading: int = Query(0),
):
    """Proxy Google Street View Static API (hides the API key from the client)."""
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
