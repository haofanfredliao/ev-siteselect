"""
arcpy_engine.py – ArcPy spatial analysis engine for EV charging site selection.

Data sources (raw_data/):
  BLU.tif                              Land-use raster (EPSG:2326, ~5 m)
  slope.tif                            Slope raster derived from DTM
  LSUG_21C_converted.shp               2021 census large sub-unit polygons (t_pop field)
  Transportation_TNM_*_CENTERLINE*.shp Road centre-line network
  download_20260401_1622_converted.shp Existing EV charger points
  GeoCom4.1_202510.csv                 POI dataset (EASTING/NORTHING in EPSG:2326)
  AdminArea_DCD_20230609.gdb_converted.shp  18-district admin boundaries

Preprocessing produces 7 normalised rasters saved to data/preprocessed/
and is designed to run once (results are cached).

Run the siting model via run_suitability_model(weights, num_sites).
"""

import json
import logging
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Path constants ────────────────────────────────────────────────────────────
_BACKEND_DIR   = os.path.dirname(os.path.abspath(__file__))
_APP_DIR       = os.path.dirname(_BACKEND_DIR)           # ev_siting_mvp/
_REPO_ROOT     = os.path.dirname(_APP_DIR)               # ev-siteselect/
RAW_DATA       = os.path.join(_REPO_ROOT, "raw_data")
PREPROCESSED   = os.path.join(_APP_DIR, "data", "preprocessed")

# Raw inputs
BLU_TIF        = os.path.join(RAW_DATA, "BLU.tif")
SLOPE_TIF      = os.path.join(RAW_DATA, "slope.tif")
LSUG_SHP       = os.path.join(RAW_DATA, "LSUG_21C_converted.shp")
CENTERLINE_SHP = os.path.join(RAW_DATA, "Transportation_TNM_20260319.gdb_CENTERLINE_converted.shp")
EV_SHP         = os.path.join(RAW_DATA, "download_20260401_1622_converted.shp")
# arcpy path parser treats ".gdb" anywhere in a path as a geodatabase indicator,
# so files with ".gdb" embedded in their name must be copied to clean names at runtime.
GEOCOM_CSV     = os.path.join(RAW_DATA, "GeoCom4.1_202510.csv")

# Preprocessed outputs
OUT_POP        = os.path.join(PREPROCESSED, "pop_density.tif")
OUT_POI        = os.path.join(PREPROCESSED, "poi_heat.tif")
OUT_ROAD       = os.path.join(PREPROCESSED, "road_dist.tif")
OUT_EV         = os.path.join(PREPROCESSED, "ev_dist.tif")
OUT_SLOPE      = os.path.join(PREPROCESSED, "slope_score.tif")
OUT_LANDUSE    = os.path.join(PREPROCESSED, "landuse_score.tif")
OUT_MASK       = os.path.join(PREPROCESSED, "landuse_mask.tif")

_ALL_OUTPUTS = [OUT_POP, OUT_POI, OUT_ROAD, OUT_EV, OUT_SLOPE, OUT_LANDUSE, OUT_MASK]

# Labels used in status reporting (order matches _ALL_OUTPUTS)
_OUTPUT_LABELS = {
    OUT_POP:     "Population Density",
    OUT_POI:     "POI Density",
    OUT_ROAD:    "Road Accessibility",
    OUT_EV:      "EV Competition",
    OUT_SLOPE:   "Slope Suitability",
    OUT_LANDUSE: "Land Use Score",
    OUT_MASK:    "Land Use Mask",
}

# Results directory for timestamped outputs
RESULTS_DIR = os.path.join(_APP_DIR, "data", "results")

# Default raw data source for each factor key
DEFAULT_SOURCES = {
    "population":         os.path.basename(LSUG_SHP),
    "poi":                os.path.basename(GEOCOM_CSV),
    "road_accessibility": os.path.basename(CENTERLINE_SHP),
    "ev_competition":     os.path.basename(EV_SHP),
    "slope":              os.path.basename(SLOPE_TIF),
    "landuse":            os.path.basename(BLU_TIF),
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _shutil_copy_shapefile(src_shp: str, dst_shp: str) -> None:
    """
    Copy a shapefile using plain shutil (bypasses arcpy path parsing).
    Copies all sidecar files that share the same stem (.dbf, .shx, .prj, .cpg, etc.)
    """
    src_base = os.path.splitext(src_shp)[0]
    dst_base = os.path.splitext(dst_shp)[0]
    src_dir  = os.path.dirname(src_shp)
    stem     = os.path.basename(src_base)
    for fname in os.listdir(src_dir):
        if fname.startswith(stem + ".") or fname == os.path.basename(src_shp):
            ext = fname[len(stem):]          # e.g.  ".shp", ".dbf", ".shx" …
            shutil.copy2(os.path.join(src_dir, fname), dst_base + ext)
    logger.info("  Copied shapefile %s → %s", os.path.basename(src_shp), os.path.basename(dst_shp))

def _setup_env(snap_raster: str) -> None:
    """Configure ArcPy environment to match the snap/reference raster."""
    import arcpy
    arcpy.env.overwriteOutput            = True
    arcpy.env.workspace                  = PREPROCESSED
    arcpy.env.snapRaster                 = snap_raster
    arcpy.env.extent                     = snap_raster
    arcpy.env.cellSize                   = snap_raster
    arcpy.env.outputCoordinateSystem     = arcpy.SpatialReference(2326)
    arcpy.env.mask                       = snap_raster


def _get_raster_stats(raster) -> tuple[float, float]:
    """Return (min, max) float statistics for an arcpy Raster object."""
    import arcpy
    r_min = float(arcpy.management.GetRasterProperties(raster, "MINIMUM").getOutput(0))
    r_max = float(arcpy.management.GetRasterProperties(raster, "MAXIMUM").getOutput(0))
    return r_min, r_max


def _normalize_raster(raster, high_is_better: bool = True,
                       out_min: float = 1.0, out_max: float = 10.0):
    """
    Min-max normalise *raster* to the [out_min, out_max] range.

    high_is_better=True  → large raw values → high score
    high_is_better=False → small raw values → high score (e.g. distance)
    """
    r_min, r_max = _get_raster_stats(raster)
    if r_max <= r_min:
        # Flat raster – fill all valid cells with mid-point score, keep NoData as NoData
        import arcpy
        mid = (out_min + out_max) / 2.0
        return arcpy.sa.Con(arcpy.sa.IsNull(raster) == 0, mid)

    span = out_max - out_min
    if high_is_better:
        return ((raster - r_min) / (r_max - r_min)) * span + out_min
    else:
        return ((r_max - raster) / (r_max - r_min)) * span + out_min


# ─── Status ───────────────────────────────────────────────────────────────────

def get_preprocessing_status() -> dict:
    """Check which preprocessed output rasters already exist on disk."""
    status = {label: os.path.exists(path)
              for path, label in _OUTPUT_LABELS.items()}
    status["all_ready"] = all(os.path.exists(p) for p in _ALL_OUTPUTS)
    return status


# ─── Per-factor preprocessing functions ───────────────────────────────────────

def _resolve_source(source: str, default: str) -> str:
    """Resolve a source filename to a full path in RAW_DATA."""
    name = source if source else default
    return os.path.join(RAW_DATA, name)


def preprocess_population(source: str = "") -> None:
    """Population density (persons / km²) from LSUG polygons."""
    import arcpy
    from arcpy import sa
    src = _resolve_source(source, os.path.basename(LSUG_SHP))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[population] Starting …")
        lsug_work = os.path.join(PREPROCESSED, "lsug_work.shp")
        if not arcpy.Exists(lsug_work):
            arcpy.conversion.FeatureClassToFeatureClass(
                os.path.join(RAW_DATA, src) if not os.path.isabs(src) else src,
                PREPROCESSED, "lsug_work.shp"
            )
        existing_fields = [f.name for f in arcpy.ListFields(lsug_work)]
        if "POP_DENS" not in existing_fields:
            arcpy.management.AddField(lsug_work, "POP_DENS", "DOUBLE")
            arcpy.management.CalculateField(
                lsug_work, "POP_DENS",
                "(!t_pop! / (!shape.area! / 1000000.0)) if !shape.area! > 0 else 0",
                "PYTHON3",
            )
        pop_raw = os.path.join(PREPROCESSED, "pop_raw.tif")
        arcpy.conversion.PolygonToRaster(
            lsug_work, "POP_DENS", pop_raw, "CELL_CENTER", "NONE", BLU_TIF
        )
        pop_score = _normalize_raster(sa.Raster(pop_raw), high_is_better=True)
        pop_score.save(OUT_POP)
        arcpy.management.Delete(pop_raw)
        logger.info("[population] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_poi(source: str = "") -> None:
    """POI density (Kernel Density from GeoCom CSV)."""
    import arcpy
    from arcpy import sa
    src = _resolve_source(source, os.path.basename(GEOCOM_CSV))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[poi] Starting …")
        sr_2326 = arcpy.SpatialReference(2326)
        poi_lyr = "geocom_xy_lyr"
        if arcpy.Exists(poi_lyr):
            arcpy.management.Delete(poi_lyr)
        arcpy.management.MakeXYEventLayer(src, "EASTING", "NORTHING", poi_lyr, sr_2326)
        ref = sa.Raster(BLU_TIF)
        cell_px = ref.meanCellWidth
        search_radius = 500
        poi_density = sa.KernelDensity(poi_lyr, "NONE", cell_px, search_radius)
        poi_score = _normalize_raster(poi_density, high_is_better=True)
        poi_score.save(OUT_POI)
        logger.info("[poi] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_road(source: str = "") -> None:
    """Road accessibility (Euclidean distance to CENTERLINE)."""
    import arcpy
    from arcpy import sa
    src = _resolve_source(source, os.path.basename(CENTERLINE_SHP))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[road] Starting …")
        centerline_clean = os.path.join(PREPROCESSED, "centerline_work.shp")
        if not os.path.exists(centerline_clean):
            _shutil_copy_shapefile(src, centerline_clean)
        arcpy.env.mask = ""
        road_dist = sa.EucDistance(centerline_clean)
        arcpy.env.mask = BLU_TIF
        road_score = _normalize_raster(road_dist, high_is_better=False)
        road_score.save(OUT_ROAD)
        logger.info("[road] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_ev(source: str = "") -> None:
    """EV competition (distance from existing chargers)."""
    import arcpy
    from arcpy import sa
    src = _resolve_source(source, os.path.basename(EV_SHP))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[ev] Starting …")
        arcpy.env.mask = ""
        ev_dist = sa.EucDistance(src)
        arcpy.env.mask = BLU_TIF
        ev_score = _normalize_raster(ev_dist, high_is_better=True)
        ev_score.save(OUT_EV)
        logger.info("[ev] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_slope(source: str = "") -> None:
    """Slope suitability."""
    import arcpy
    from arcpy import sa
    src = _resolve_source(source, os.path.basename(SLOPE_TIF))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[slope] Starting …")
        slope_r = sa.Raster(src)
        slope_score = _normalize_raster(slope_r, high_is_better=False)
        slope_score.save(OUT_SLOPE)
        logger.info("[slope] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_landuse(source: str = "") -> None:
    """Land-use score + binary mask from BLU.tif."""
    import arcpy
    from arcpy import sa
    src = _resolve_source(source, os.path.basename(BLU_TIF))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[landuse] Starting …")
        remap = sa.RemapValue([
            [1,  6], [2,  5], [3,  3], [11, 10],
            [21, 4], [22, 4], [23, 3],
            [31, 7], [32, 6], [41, 7], [42, 5], [43, 4], [44, 4],
            [51, 2], [52, 5], [53, 6], [54, 3],
            [61, 2], [62, 2],
            [71, "NODATA"], [72, "NODATA"], [73, "NODATA"], [74, "NODATA"],
            [83, "NODATA"], [91, "NODATA"], [92, "NODATA"],
        ])
        landuse_score = sa.Reclassify(src, "VALUE", remap, "NODATA")
        landuse_score.save(OUT_LANDUSE)
        mask_r = sa.Con(sa.IsNull(landuse_score), 0, 1)
        mask_r.save(OUT_MASK)
        logger.info("[landuse] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


# Dispatch table for per-factor preprocessing
PREPROCESS_FUNCS = {
    "population":         preprocess_population,
    "poi":                preprocess_poi,
    "road_accessibility": preprocess_road,
    "ev_competition":     preprocess_ev,
    "slope":              preprocess_slope,
    "landuse":            preprocess_landuse,
}


# ─── Preprocessing pipeline (all-in-one convenience) ──────────────────────────

def preprocess_all() -> None:
    """
    One-time preprocessing: converts all raw datasets into normalised
    score rasters (1–10 scale) saved in data/preprocessed/.
    """
    logger.info("=== Starting EV Siting Preprocessing (all factors) ===")
    for key, func in PREPROCESS_FUNCS.items():
        func()
    logger.info("=== Preprocessing complete. Outputs in: %s ===", PREPROCESSED)


# ─── Suitability model ────────────────────────────────────────────────────────

def run_suitability_model(weights: dict, num_sites: int = 5) -> dict:
    """
    Run the weighted multi-criteria suitability model.

    Parameters
    ----------
    weights : dict
        Keys: population, poi, road_accessibility, ev_competition, slope, landuse
        Values: non-negative floats (will be normalised to sum = 1).
    num_sites : int
        Number of top candidate sites to return.

    Returns
    -------
    dict
        GeoJSON FeatureCollection in WGS84 (EPSG:4326).
    """
    import arcpy
    from arcpy import sa

    # Validate preprocessing
    missing = [p for p in _ALL_OUTPUTS if not os.path.exists(p)]
    if missing:
        labels = [_OUTPUT_LABELS.get(p, p) for p in missing]
        raise RuntimeError(
            f"Preprocessed rasters not found ({', '.join(labels)}). "
            "Please call POST /api/preprocess first and wait for it to complete."
        )

    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = PREPROCESSED

    try:
        # Load normalised score rasters
        pop     = sa.Raster(OUT_POP)
        poi     = sa.Raster(OUT_POI)
        road    = sa.Raster(OUT_ROAD)
        ev      = sa.Raster(OUT_EV)
        slope   = sa.Raster(OUT_SLOPE)
        landuse = sa.Raster(OUT_LANDUSE)
        mask    = sa.Raster(OUT_MASK)

        # Extract and normalise weights
        w = {
            "population":          max(0.0, float(weights.get("population",          1))),
            "poi":                 max(0.0, float(weights.get("poi",                 1))),
            "road_accessibility":  max(0.0, float(weights.get("road_accessibility",  1))),
            "ev_competition":      max(0.0, float(weights.get("ev_competition",      1))),
            "slope":               max(0.0, float(weights.get("slope",              1))),
            "landuse":             max(0.0, float(weights.get("landuse",             1))),
        }
        total = sum(w.values()) or 1.0
        for k in w:
            w[k] /= total

        logger.info(
            "Weights → pop=%.3f poi=%.3f road=%.3f ev=%.3f slope=%.3f landuse=%.3f",
            w["population"], w["poi"], w["road_accessibility"],
            w["ev_competition"], w["slope"], w["landuse"],
        )

        # Weighted sum
        weighted_sum = (
            pop     * w["population"]         +
            poi     * w["poi"]                +
            road    * w["road_accessibility"]  +
            ev      * w["ev_competition"]      +
            slope   * w["slope"]               +
            landuse * w["landuse"]
        )

        # Apply land-use mask: restricted cells become NoData
        final_raster = sa.SetNull(mask == 0, weighted_sum)

        out_final = os.path.join(PREPROCESSED, "final_score.tif")
        final_raster.save(out_final)

        # ── Downsample to 200 m for manageable point extraction ───────────────
        out_200m = os.path.join(PREPROCESSED, "final_score_200m.tif")
        arcpy.management.Resample(out_final, out_200m, "200", "BILINEAR")
        final_200m = sa.Raster(out_200m)

        r_min, r_max = _get_raster_stats(final_200m)
        # Keep top 5 % of value range as candidate cells
        threshold = r_max - (r_max - r_min) * 0.05
        top_raster = sa.Con(final_200m >= threshold, final_200m)

        # ── RasterToPoint → candidate list ────────────────────────────────────
        temp_pts = os.path.join(PREPROCESSED, "tmp_candidates.shp")
        arcpy.conversion.RasterToPoint(top_raster, temp_pts, "VALUE")

        rows: list[tuple[float, float, float]] = []   # (x_2326, y_2326, score)
        with arcpy.da.SearchCursor(temp_pts, ["SHAPE@XY", "grid_code"]) as cur:
            for r in cur:
                rows.append((r[0][0], r[0][1], float(r[1])))
        rows.sort(key=lambda r: r[2], reverse=True)

        # ── Spatially dispersed selection (min 300 m spacing) ─────────────────
        MIN_DIST_M = 300.0
        selected: list[tuple[float, float, float]] = []
        for x, y, score in rows:
            if any(
                (x - sx) ** 2 + (y - sy) ** 2 < MIN_DIST_M ** 2
                for sx, sy, _ in selected
            ):
                continue
            selected.append((x, y, score))
            if len(selected) >= num_sites:
                break

        if not selected:
            logger.warning("No candidate sites found – returning empty FeatureCollection.")
            return {"type": "FeatureCollection", "features": []}

        # ── Project EPSG:2326 → WGS84 (EPSG:4326) ────────────────────────────
        sr_2326 = arcpy.SpatialReference(2326)
        sr_4326 = arcpy.SpatialReference(4326)

        features = []
        for rank, (x, y, score) in enumerate(selected, 1):
            pt      = arcpy.Point(x, y)
            geom    = arcpy.PointGeometry(pt, sr_2326)
            geom_wgs = geom.projectAs(sr_4326)
            lon = round(geom_wgs.firstPoint.X, 6)
            lat = round(geom_wgs.firstPoint.Y, 6)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"score": round(score, 4), "rank": rank},
            })

        geojson = {"type": "FeatureCollection", "features": features}
        # Auto-save with timestamp
        save_result_geojson(geojson)
        return geojson

    finally:
        # Clean up temp files
        for tmp in ["tmp_candidates.shp"]:
            tmp_path = os.path.join(PREPROCESSED, tmp)
            try:
                if arcpy.Exists(tmp_path):
                    arcpy.management.Delete(tmp_path)
            except Exception:
                pass
        arcpy.CheckInExtension("Spatial")


# ─── Result persistence ───────────────────────────────────────────────────────

def save_result_geojson(geojson: dict) -> str:
    """Save a GeoJSON result with a timestamp filename. Returns the filename."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"result_{ts}.geojson"
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    logger.info("Saved result → %s", filename)
    return filename


def list_saved_results() -> list[dict]:
    """Return a list of saved result files sorted newest-first."""
    if not os.path.isdir(RESULTS_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(RESULTS_DIR) if f.endswith(".geojson")],
        reverse=True,
    )
    results = []
    for f in files:
        fp = os.path.join(RESULTS_DIR, f)
        results.append({
            "filename": f,
            "timestamp": f.replace("result_", "").replace(".geojson", ""),
            "size_kb": round(os.path.getsize(fp) / 1024, 1),
        })
    return results


def load_result_file(filename: str) -> dict:
    """Load a previously saved GeoJSON result by filename."""
    path = os.path.join(RESULTS_DIR, os.path.basename(filename))
    if not os.path.exists(path):
        raise FileNotFoundError(f"Result file not found: {filename}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_raw_sources() -> dict:
    """List available raw data files grouped by extension."""
    if not os.path.isdir(RAW_DATA):
        return {}
    files = os.listdir(RAW_DATA)
    shapefiles = sorted(set(f for f in files if f.endswith(".shp")))
    csvfiles = sorted(f for f in files if f.endswith(".csv"))
    tiffiles = sorted(f for f in files if f.endswith(".tif"))
    return {
        "shapefiles": shapefiles,
        "csv": csvfiles,
        "tif": tiffiles,
        "defaults": DEFAULT_SOURCES,
    }
