"""
HK EV Charging Station Site Selection - FastAPI Backend
Run with:  uvicorn main:app --reload --port 8000
"""

import logging
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HK EV Charging Site Selection API",
    version="1.0.0",
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

# Serve the frontend at /app  (optional – also works when opened as a plain file)
_FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)
if os.path.exists(_FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

# ─── Request / Response Models ────────────────────────────────────────────────

class SitingRequest(BaseModel):
    weights: dict  # keys: population, poi, road_accessibility, ev_competition, slope, landuse
    num_sites: int = 5


# ─── Preprocessing state ──────────────────────────────────────────────────────

_preprocessing_running: bool = False


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


@app.post("/api/preprocess", tags=["preprocessing"])
def trigger_preprocess(background_tasks: BackgroundTasks):
    """
    Start the one-time data preprocessing pipeline in the background.
    Expected runtime: 10–30 minutes depending on hardware.
    Poll /api/status to monitor progress.
    """
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
        "message": (
            "Preprocessing started in the background. "
            "This may take 15–30 minutes. "
            "Poll GET /api/status to track progress."
        ),
    }


@app.post("/api/siting", tags=["analysis"])
def compute_siting(request: SitingRequest):
    """
    Run the weighted suitability model and return the top N candidate
    EV charging sites as a GeoJSON FeatureCollection.
    """
    if request.num_sites < 1 or request.num_sites > 50:
        raise HTTPException(status_code=422, detail="num_sites must be between 1 and 50.")

    try:
        from arcpy_engine import run_suitability_model
        result = run_suitability_model(request.weights, request.num_sites)
        return result
    except RuntimeError as exc:
        # Caller error (e.g. preprocessing not done)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Siting analysis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
