"""
arcpy_engine.py – ArcPy spatial analysis engine for EV charging site selection.

Enhanced from ev_siting_mvp with:
  - TYPE-weighted POI Kernel Density (GeoCom 4.1 TYPE field, 800 m radius)
  - Road DistanceAccumulation with slope cost surface (1 + slope*0.05)
  - 18-district study area masking (AdminArea.shp, NAME_EN filter)
  - 200 m downsampled rasters auto-generated at preprocessing for fast analysis
  - Raster overlay export (50 m PNG + WGS84 bounds)
  - Vector layer export (GeoJSON WGS84)

Data sources (raw_data/):
  BLU.tif                   Land-use raster (EPSG:2326, ~5 m)
  slope.tif                 Slope raster derived from DTM
  LSUG_21C_converted.shp    2021 census large sub-unit polygons
  Transportation_TNM_*_CENTERLINE*.shp  Road centre-line network
  download_20260401_1622_converted.shp  Existing EV charger points
  GeoCom4.1_202510.csv      POI dataset (EASTING/NORTHING in EPSG:2326)
  AdminArea.shp             18-district admin boundaries (NAME_EN / NAME_TC)
"""

import json
import logging
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Path constants ────────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT   = os.path.dirname(_BACKEND_DIR)
RAW_DATA     = os.path.join(_REPO_ROOT, "raw_data")
PREPROCESSED = os.path.join(_BACKEND_DIR, "data", "preprocessed")

# Raw inputs
BLU_TIF        = os.path.join(RAW_DATA, "BLU.tif")
SLOPE_TIF      = os.path.join(RAW_DATA, "slope.tif")
LSUG_SHP       = os.path.join(RAW_DATA, "LSUG_21C_converted.shp")
CENTERLINE_SHP = os.path.join(
    RAW_DATA, "Transportation_TNM_20260319.gdb_CENTERLINE_converted.shp"
)
EV_SHP    = os.path.join(RAW_DATA, "download_20260401_1622_converted.shp")
GEOCOM_CSV = os.path.join(RAW_DATA, "GeoCom4.1_202510.csv")
ADMIN_SHP  = os.path.join(RAW_DATA, "AdminArea.shp")   # clean name, no .gdb in path

# Preprocessed full-resolution outputs
OUT_POP     = os.path.join(PREPROCESSED, "pop_density.tif")
OUT_POI     = os.path.join(PREPROCESSED, "poi_heat.tif")
OUT_ROAD    = os.path.join(PREPROCESSED, "road_dist.tif")
OUT_EV      = os.path.join(PREPROCESSED, "ev_dist.tif")
OUT_SLOPE   = os.path.join(PREPROCESSED, "slope_score.tif")
OUT_LANDUSE = os.path.join(PREPROCESSED, "landuse_score.tif")
OUT_MASK    = os.path.join(PREPROCESSED, "landuse_mask.tif")

# 200 m downsampled versions (for fast siting analysis, ~400× fewer pixels)
OUT_POP_200     = os.path.join(PREPROCESSED, "pop_density_200m.tif")
OUT_POI_200     = os.path.join(PREPROCESSED, "poi_heat_200m.tif")
OUT_ROAD_200    = os.path.join(PREPROCESSED, "road_dist_200m.tif")
OUT_EV_200      = os.path.join(PREPROCESSED, "ev_dist_200m.tif")
OUT_SLOPE_200   = os.path.join(PREPROCESSED, "slope_score_200m.tif")
OUT_LANDUSE_200 = os.path.join(PREPROCESSED, "landuse_score_200m.tif")
OUT_MASK_200    = os.path.join(PREPROCESSED, "landuse_mask_200m.tif")

_ALL_OUTPUTS = [OUT_POP, OUT_POI, OUT_ROAD, OUT_EV, OUT_SLOPE, OUT_LANDUSE, OUT_MASK]

_OUTPUT_LABELS = {
    OUT_POP:     "Population Density",
    OUT_POI:     "POI Density",
    OUT_ROAD:    "Road Accessibility",
    OUT_EV:      "EV Competition",
    OUT_SLOPE:   "Slope Suitability",
    OUT_LANDUSE: "Land Use Score",
    OUT_MASK:    "Land Use Mask",
}

RESULTS_DIR = os.path.join(_BACKEND_DIR, "data", "results")

DEFAULT_SOURCES = {
    "population":         os.path.basename(LSUG_SHP),
    "poi":                os.path.basename(GEOCOM_CSV),
    "road_accessibility": os.path.basename(CENTERLINE_SHP),
    "ev_competition":     os.path.basename(EV_SHP),
    "slope":              os.path.basename(SLOPE_TIF),
    "landuse":            os.path.basename(BLU_TIF),
}

# ─── POI TYPE weights (GeoCom 4.1 TYPE field → EV dwell-time relevance) ──────
# Higher = longer expected dwell time = higher EV charging demand
# Unknown TYPE codes fall back to DEFAULT_POI_WEIGHT = 1
POI_TYPE_WEIGHTS = {
    # Weight 5: High-dwell commercial / parking
    "MAL": 5, "ROI": 5, "HTL": 5, "CPO": 5, "SMK": 5,
    # Weight 4: Entertainment / leisure / sports
    "CHL": 4, "PFM": 4, "EXB": 4, "TNC": 4, "IGH": 4,
    "STD": 4, "SPL": 4, "GCL": 4, "REC": 4,
    # Weight 3: Medical / transport hub / education
    "HOS": 3, "CLI": 3, "TEI": 3, "RSN": 3,
    "MTA": 3, "FET": 3, "CMC": 3, "TRH": 3,
    # Weight 2: Schools / offices / banking
    "PRS": 2, "SES": 2, "KDG": 2, "POF": 2,
    "LIB": 2, "GOF": 2, "BNK": 2,
    # Weight 1: Low-dwell convenience
    "CVS": 1, "BUS": 1, "PET": 1, "POB": 1, "MIN": 1,
    # Weight 0: Exclude (parks, nature, military, utilities)
    "PAK": 0, "BGD": 0, "UTI": 0, "TRF": 0,
    "CEM": 0, "MIL": 0, "SEA": 0,
}
DEFAULT_POI_WEIGHT = 1

# ─── Raster layer registry (for overlay export endpoint) ─────────────────────
RASTER_OVERLAY_REGISTRY = {
    "pop_density":   OUT_POP,
    "poi_heat":      OUT_POI,
    "road_dist":     OUT_ROAD,
    "ev_dist":       OUT_EV,
    "slope_score":   OUT_SLOPE,
    "landuse_score": OUT_LANDUSE,
    "final_score":   os.path.join(PREPROCESSED, "final_score.tif"),
}


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _shutil_copy_shapefile(src_shp: str, dst_shp: str) -> None:
    """Copy all shapefile sidecar files using shutil (avoids arcpy path parsing)."""
    src_base = os.path.splitext(src_shp)[0]
    dst_base = os.path.splitext(dst_shp)[0]
    src_dir  = os.path.dirname(src_shp)
    stem     = os.path.basename(src_base)
    for fname in os.listdir(src_dir):
        if fname.startswith(stem + ".") or fname == os.path.basename(src_shp):
            ext = fname[len(stem):]
            shutil.copy2(os.path.join(src_dir, fname), dst_base + ext)
    logger.info("  Copied shapefile %s → %s", os.path.basename(src_shp), os.path.basename(dst_shp))


def _setup_env(snap_raster: str) -> None:
    """Configure ArcPy environment to match the snap/reference raster."""
    import arcpy
    arcpy.env.overwriteOutput        = True
    arcpy.env.workspace              = PREPROCESSED
    arcpy.env.snapRaster             = snap_raster
    arcpy.env.extent                 = snap_raster
    arcpy.env.cellSize               = snap_raster
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(2326)
    arcpy.env.mask                   = snap_raster


def _get_raster_stats(raster) -> tuple:
    import arcpy
    r_min = float(arcpy.management.GetRasterProperties(raster, "MINIMUM").getOutput(0))
    r_max = float(arcpy.management.GetRasterProperties(raster, "MAXIMUM").getOutput(0))
    return r_min, r_max


def _normalize_raster(raster, high_is_better: bool = True,
                       out_min: float = 1.0, out_max: float = 10.0):
    """Min-max normalise raster to [out_min, out_max]."""
    r_min, r_max = _get_raster_stats(raster)
    if r_max <= r_min:
        import arcpy
        mid = (out_min + out_max) / 2.0
        return arcpy.sa.Con(arcpy.sa.IsNull(raster) == 0, mid)
    span = out_max - out_min
    if high_is_better:
        return ((raster - r_min) / (r_max - r_min)) * span + out_min
    else:
        return ((r_max - raster) / (r_max - r_min)) * span + out_min


def _save_200m(full_res_tif: str, out_200m: str) -> None:
    """Downsample a raster to 200 m (BILINEAR) for fast analysis."""
    import arcpy
    arcpy.management.Resample(full_res_tif, out_200m, "200", "BILINEAR")
    logger.info("  200 m version: %s", os.path.basename(out_200m))


def _numpy_rgba_to_png(rgba) -> bytes:
    """Encode (H, W, 4) uint8 numpy array as PNG – pure Python, no PIL required."""
    import struct, zlib
    H, W = rgba.shape[:2]

    def chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig  = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
    raw  = bytearray()
    for row in rgba:
        raw.append(0)          # filter type = None
        raw.extend(row.tobytes())
    idat = chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ─── Status ───────────────────────────────────────────────────────────────────

def get_preprocessing_status() -> dict:
    status = {label: os.path.exists(path) for path, label in _OUTPUT_LABELS.items()}
    status["all_ready"] = all(os.path.exists(p) for p in _ALL_OUTPUTS)
    return status


def _resolve_source(source: str, default: str) -> str:
    name = source if source else default
    return os.path.join(RAW_DATA, name)


# ─── District helpers ─────────────────────────────────────────────────────────

def list_districts() -> list:
    """Return sorted list of 18-district English names from AdminArea.shp."""
    import arcpy
    return sorted(set(r[0] for r in arcpy.da.SearchCursor(ADMIN_SHP, ["NAME_EN"])))


def get_districts_geojson() -> dict:
    """Return WGS84 GeoJSON FeatureCollection for all 18 districts."""
    import arcpy
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.env.overwriteOutput = True
    tmp_json = os.path.join(PREPROCESSED, "tmp_districts.geojson")
    try:
        arcpy.conversion.FeaturesToJSON(
            ADMIN_SHP, tmp_json,
            geoJSON="GEOJSON",
            outputToWGS84="WGS84",
        )
        with open(tmp_json, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        # Slim down properties to only what the frontend needs
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            feat["properties"] = {
                "name_en": p.get("NAME_EN", ""),
                "name_tc": p.get("NAME_TC", ""),
                "code":    p.get("AREA_CODE", ""),
            }
        return data
    finally:
        if os.path.exists(tmp_json):
            os.remove(tmp_json)


# ─── Per-factor preprocessing ─────────────────────────────────────────────────

def preprocess_population(source: str = "") -> None:
    """Population density (persons/km²) from LSUG polygons → pop_density.tif + 200 m."""
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
                PREPROCESSED, "lsug_work.shp",
            )
        if "POP_DENS" not in [f.name for f in arcpy.ListFields(lsug_work)]:
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
        _save_200m(OUT_POP, OUT_POP_200)
        logger.info("[population] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_poi(source: str = "") -> None:
    """
    TYPE-weighted POI Kernel Density from GeoCom CSV.
    Writes a WEIGHT column from POI_TYPE_WEIGHTS lookup, then uses it as
    the population field in KernelDensity (search radius 800 m).
    """
    import arcpy
    from arcpy import sa
    import csv as csv_module
    src = _resolve_source(source, os.path.basename(GEOCOM_CSV))
    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)
    try:
        logger.info("[poi] Starting …")
        sr_2326 = arcpy.SpatialReference(2326)

        # Build a weighted CSV in the workspace (TYPE → WEIGHT lookup)
        weighted_csv = os.path.join(PREPROCESSED, "geocom_weighted.csv")
        with open(src, "r", encoding="utf-8-sig") as fin, \
             open(weighted_csv, "w", encoding="utf-8", newline="") as fout:
            reader = csv_module.DictReader(fin)
            fieldnames = list(reader.fieldnames) + ["WEIGHT"]
            writer = csv_module.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                t = str(row.get("TYPE", "")).strip().upper()
                w = POI_TYPE_WEIGHTS.get(t, DEFAULT_POI_WEIGHT)
                if w == 0:
                    continue   # skip excluded types
                row["WEIGHT"] = w
                writer.writerow(row)

        poi_lyr = "geocom_weighted_lyr"
        if arcpy.Exists(poi_lyr):
            arcpy.management.Delete(poi_lyr)
        arcpy.management.MakeXYEventLayer(
            weighted_csv, "EASTING", "NORTHING", poi_lyr, sr_2326
        )
        cell_px = sa.Raster(BLU_TIF).meanCellWidth
        poi_density = sa.KernelDensity(poi_lyr, "WEIGHT", cell_px, 800)
        poi_score = _normalize_raster(poi_density, high_is_better=True)
        poi_score.save(OUT_POI)
        _save_200m(OUT_POI, OUT_POI_200)
        logger.info("[poi] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_road(source: str = "") -> None:
    """
    Road accessibility using DistanceAccumulation + slope cost surface.
    Cost raster = 1 + slope_percent * 0.05
    (flat ground: cost 1.0 ; 20 % slope: cost 2.0 ; 45 %: cost 3.25)
    """
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

        slope_r = sa.Raster(SLOPE_TIF)
        cost_surface = 1.0 + slope_r * 0.05

        arcpy.env.mask = ""
        road_dist = sa.DistanceAccumulation(
            centerline_clean,
            in_cost_raster=cost_surface,
        )
        arcpy.env.mask = BLU_TIF
        road_score = _normalize_raster(road_dist, high_is_better=False)
        road_score.save(OUT_ROAD)
        _save_200m(OUT_ROAD, OUT_ROAD_200)
        logger.info("[road] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_ev(source: str = "") -> None:
    """EV competition (Euclidean distance from existing chargers)."""
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
        _save_200m(OUT_EV, OUT_EV_200)
        logger.info("[ev] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_slope(source: str = "") -> None:
    """Slope suitability (lower slope → higher score)."""
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
        _save_200m(OUT_SLOPE, OUT_SLOPE_200)
        logger.info("[slope] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


def preprocess_landuse(source: str = "") -> None:
    """Land-use score + binary mask from BLU.tif reclassification."""
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
        _save_200m(OUT_LANDUSE, OUT_LANDUSE_200)
        _save_200m(OUT_MASK,    OUT_MASK_200)
        logger.info("[landuse] Done.")
    finally:
        arcpy.CheckInExtension("Spatial")


PREPROCESS_FUNCS = {
    "population":         preprocess_population,
    "poi":                preprocess_poi,
    "road_accessibility": preprocess_road,
    "ev_competition":     preprocess_ev,
    "slope":              preprocess_slope,
    "landuse":            preprocess_landuse,
}


def preprocess_all() -> None:
    logger.info("=== Starting EV Siting Preprocessing (all factors) ===")
    for key, func in PREPROCESS_FUNCS.items():
        func()
    logger.info("=== Preprocessing complete. Outputs in: %s ===", PREPROCESSED)


# ─── Suitability model ────────────────────────────────────────────────────────

def run_suitability_model(
    weights: dict,
    num_sites: int = 5,
    study_area: list = None,
) -> dict:
    """
    Run weighted multi-criteria suitability model.

    Uses 200 m rasters when available (~400× fewer pixels than 5 m full-res).
    Optionally clips analysis to selected districts via ExtractByMask.

    Returns GeoJSON FeatureCollection (WGS84, EPSG:4326).
    """
    import arcpy
    from arcpy import sa
    import numpy as np

    missing = [p for p in _ALL_OUTPUTS if not os.path.exists(p)]
    if missing:
        labels = [_OUTPUT_LABELS.get(p, p) for p in missing]
        raise RuntimeError(
            f"Preprocessed rasters not found ({', '.join(labels)}). "
            "Run POST /api/preprocess first."
        )

    def _load(full, low):
        return sa.Raster(low) if os.path.exists(low) else sa.Raster(full)

    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = PREPROCESSED

    try:
        pop     = _load(OUT_POP,     OUT_POP_200)
        poi     = _load(OUT_POI,     OUT_POI_200)
        road    = _load(OUT_ROAD,    OUT_ROAD_200)
        ev      = _load(OUT_EV,      OUT_EV_200)
        slope   = _load(OUT_SLOPE,   OUT_SLOPE_200)
        landuse = _load(OUT_LANDUSE, OUT_LANDUSE_200)
        mask    = _load(OUT_MASK,    OUT_MASK_200)

        w = {
            "population":         max(0.0, float(weights.get("population",         1))),
            "poi":                max(0.0, float(weights.get("poi",                1))),
            "road_accessibility": max(0.0, float(weights.get("road_accessibility", 1))),
            "ev_competition":     max(0.0, float(weights.get("ev_competition",     1))),
            "slope":              max(0.0, float(weights.get("slope",             1))),
            "landuse":            max(0.0, float(weights.get("landuse",            1))),
        }
        total = sum(w.values()) or 1.0
        for k in w:
            w[k] /= total

        logger.info(
            "Weights → pop=%.3f poi=%.3f road=%.3f ev=%.3f slope=%.3f landuse=%.3f",
            w["population"], w["poi"], w["road_accessibility"],
            w["ev_competition"], w["slope"], w["landuse"],
        )

        weighted_sum = (
            pop     * w["population"]         +
            poi     * w["poi"]                +
            road    * w["road_accessibility"]  +
            ev      * w["ev_competition"]      +
            slope   * w["slope"]               +
            landuse * w["landuse"]
        )

        # Apply land-use mask (restricted cells → NoData)
        final_raster = sa.SetNull(mask == 0, weighted_sum)

        # Optionally clip to study area districts
        if study_area:
            quoted = ", ".join(f"'{n}'" for n in study_area)
            where_clause = f"NAME_EN IN ({quoted})"
            temp_study = os.path.join(PREPROCESSED, "tmp_study_area.shp")
            arcpy.analysis.Select(ADMIN_SHP, temp_study, where_clause)
            final_raster = sa.ExtractByMask(final_raster, temp_study)

        out_final = os.path.join(PREPROCESSED, "final_score.tif")
        final_raster.save(out_final)

        # ── NumPy candidate extraction (replaces slow RasterToPoint) ─────────
        NODATA_VAL = -9999.0
        arr = arcpy.RasterToNumPyArray(out_final, nodata_to_value=NODATA_VAL)
        nrows, ncols = arr.shape

        desc = arcpy.Describe(out_final)
        xll  = desc.extent.XMin
        yll  = desc.extent.YMin
        cell = float(
            arcpy.management.GetRasterProperties(out_final, "CELLSIZEX").getOutput(0)
        )

        valid = arr != NODATA_VAL
        rows_idx, cols_idx = np.where(valid)
        values = arr[rows_idx, cols_idx]

        if len(values) == 0:
            logger.warning("No candidate cells after masking – returning empty result.")
            return {"type": "FeatureCollection", "features": []}

        order  = np.argsort(values)[::-1]
        rows_s = rows_idx[order]
        cols_s = cols_idx[order]
        vals_s = values[order]

        # Pixel index → EPSG:2326 coordinates
        x_coords = xll + (cols_s + 0.5) * cell
        y_coords = yll + (nrows - rows_s - 0.5) * cell   # raster rows: top→bottom

        # Dispersed selection: minimum 300 m spacing
        MIN_DIST_SQ = 300.0 ** 2
        selected = []
        for i in range(len(rows_s)):
            x, y, score = float(x_coords[i]), float(y_coords[i]), float(vals_s[i])
            if any(
                (x - sx) ** 2 + (y - sy) ** 2 < MIN_DIST_SQ
                for sx, sy, _ in selected
            ):
                continue
            selected.append((x, y, score))
            if len(selected) >= num_sites:
                break

        if not selected:
            logger.warning("No dispersed sites found.")
            return {"type": "FeatureCollection", "features": []}

        # Project EPSG:2326 → WGS84
        sr_2326 = arcpy.SpatialReference(2326)
        sr_4326 = arcpy.SpatialReference(4326)
        features = []
        for rank, (x, y, score) in enumerate(selected, 1):
            geom_wgs = arcpy.PointGeometry(arcpy.Point(x, y), sr_2326).projectAs(sr_4326)
            lon = round(geom_wgs.firstPoint.X, 6)
            lat = round(geom_wgs.firstPoint.Y, 6)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"score": round(score, 4), "rank": rank},
            })

        geojson = {"type": "FeatureCollection", "features": features}
        save_result_geojson(geojson)
        return geojson

    finally:
        # Clean up temp study area shapefile
        for ext in [".shp", ".dbf", ".shx", ".prj", ".cpg"]:
            p = os.path.join(PREPROCESSED, "tmp_study_area" + ext)
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        arcpy.CheckInExtension("Spatial")


# ─── Layer export ─────────────────────────────────────────────────────────────

def export_raster_overlay(name: str) -> dict:
    """
    Export a preprocessed raster as a colorised PNG (50 m resolution) with
    WGS84 bounding box for Leaflet ImageOverlay.

    Returns {"png_base64": str, "bounds": [[lat_min, lng_min], [lat_max, lng_max]], "name": str}.
    """
    import arcpy
    import numpy as np
    import base64

    raster_path = RASTER_OVERLAY_REGISTRY.get(name)
    if not raster_path or not os.path.exists(raster_path):
        raise FileNotFoundError(f"Raster overlay not available: '{name}'")

    arcpy.env.overwriteOutput = True
    tmp_50m      = os.path.join(PREPROCESSED, f"tmp_overlay_{name}.tif")
    tmp_50m_wgs84 = os.path.join(PREPROCESSED, f"tmp_overlay_{name}_wgs84.tif")
    try:
        # 1. Downsample to 50 m in native projection (HK1980)
        arcpy.management.Resample(raster_path, tmp_50m, "50", "BILINEAR")

        # 2. Reproject to WGS84 so that the PNG pixels align with Leaflet's
        #    lat/lng coordinate space — this eliminates the HK1980→WGS84 shear
        sr_4326 = arcpy.SpatialReference(4326)
        arcpy.management.ProjectRaster(
            tmp_50m, tmp_50m_wgs84, sr_4326,
            resampling_type="BILINEAR",
        )

        # 3. Derive WGS84 bounds from the reprojected raster extent
        desc = arcpy.Describe(tmp_50m_wgs84)
        ext  = desc.extent
        bounds = [
            [round(ext.YMin, 6), round(ext.XMin, 6)],
            [round(ext.YMax, 6), round(ext.XMax, 6)],
        ]

        # 4. Read as NumPy array (already in WGS84 — rows align with lat)
        SENTINEL = -9999.0
        arr  = arcpy.RasterToNumPyArray(tmp_50m_wgs84, nodata_to_value=SENTINEL)
        nrows, ncols = arr.shape
        valid = arr != SENTINEL
        arr_f = arr.astype(float)

        # Normalise valid pixels to [0, 1]
        norm = np.zeros_like(arr_f)
        vv = arr_f[valid]
        if len(vv):
            vmin, vmax = vv.min(), vv.max()
            span = vmax - vmin if vmax > vmin else 1.0
            norm[valid] = (arr_f[valid] - vmin) / span

        # Colormap: high value → green, low → red  (RdYlGn direction)
        v = norm
        r = np.where(v < 0.5, v * 2 * 255,       255 - (v - 0.5) * 70).clip(0, 255)
        g = np.where(v < 0.5, 200 + v * 40,       220 - (v - 0.5) * 440).clip(0, 255)
        b = np.where(v < 0.5, 80  - v * 160,      0).clip(0, 255)

        rgba = np.zeros((nrows, ncols, 4), dtype=np.uint8)
        rgba[:, :, 0] = np.where(valid, r, 0).astype(np.uint8)
        rgba[:, :, 1] = np.where(valid, g, 0).astype(np.uint8)
        rgba[:, :, 2] = np.where(valid, b, 0).astype(np.uint8)
        rgba[:, :, 3] = np.where(valid, 170, 0).astype(np.uint8)   # ~67 % opacity

        png_bytes = _numpy_rgba_to_png(rgba)
        png_b64   = base64.b64encode(png_bytes).decode("ascii")

        return {"png_base64": png_b64, "bounds": bounds, "name": name}
    finally:
        try:
            if os.path.exists(tmp_50m):
                arcpy.management.Delete(tmp_50m)
        except Exception:
            pass
        try:
            if os.path.exists(tmp_50m_wgs84):
                arcpy.management.Delete(tmp_50m_wgs84)
        except Exception:
            pass


def export_vector_layer(name: str) -> dict:
    """
    Export a vector layer as WGS84 GeoJSON.
    Supported names: 'ev_charger', 'population', 'districts', 'poi_sample'.
    """
    import arcpy

    REGISTRY = {
        "ev_charger":  EV_SHP,
        "population":  LSUG_SHP,
        "districts":   ADMIN_SHP,
    }

    os.makedirs(PREPROCESSED, exist_ok=True)
    arcpy.env.overwriteOutput = True
    tmp_json = os.path.join(PREPROCESSED, f"tmp_vector_{name}.geojson")

    try:
        if name == "poi_sample":
            return _export_poi_sample()

        src_shp = REGISTRY.get(name)
        if not src_shp:
            raise ValueError(f"Unknown vector layer: '{name}'")
        if not os.path.exists(src_shp):
            raise FileNotFoundError(f"Source not found: {src_shp}")

        arcpy.conversion.FeaturesToJSON(
            src_shp, tmp_json,
            geoJSON="GEOJSON",
            outputToWGS84="WGS84",
        )
        with open(tmp_json, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    finally:
        if os.path.exists(tmp_json):
            os.remove(tmp_json)


def _export_poi_sample(max_features: int = 5000) -> dict:
    """Export up to max_features POI points from GeoCom CSV as WGS84 GeoJSON."""
    import arcpy
    import csv as csv_module

    sr_2326 = arcpy.SpatialReference(2326)
    sr_4326 = arcpy.SpatialReference(4326)
    features = []
    with open(GEOCOM_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            if len(features) >= max_features:
                break
            try:
                x = float(row["EASTING"])
                y = float(row["NORTHING"])
            except (ValueError, KeyError):
                continue
            poi_type = str(row.get("TYPE", "")).strip().upper()
            weight = POI_TYPE_WEIGHTS.get(poi_type, DEFAULT_POI_WEIGHT)
            if weight == 0:
                continue
            geom_wgs = arcpy.PointGeometry(arcpy.Point(x, y), sr_2326).projectAs(sr_4326)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(geom_wgs.firstPoint.X, 5),
                        round(geom_wgs.firstPoint.Y, 5),
                    ],
                },
                "properties": {
                    "name":   str(row.get("NAME_EN", "")).strip(),
                    "type":   poi_type,
                    "weight": weight,
                },
            })
    return {"type": "FeatureCollection", "features": features}


# ─── Result persistence ───────────────────────────────────────────────────────

def save_result_geojson(geojson: dict) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"result_{ts}.geojson"
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    logger.info("Saved result → %s", filename)
    return filename


def list_saved_results() -> list:
    if not os.path.isdir(RESULTS_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(RESULTS_DIR) if f.endswith(".geojson")],
        reverse=True,
    )
    return [
        {
            "filename":  f,
            "timestamp": f.replace("result_", "").replace(".geojson", ""),
            "size_kb":   round(os.path.getsize(os.path.join(RESULTS_DIR, f)) / 1024, 1),
        }
        for f in files
    ]


def load_result_file(filename: str) -> dict:
    path = os.path.join(RESULTS_DIR, os.path.basename(filename))
    if not os.path.exists(path):
        raise FileNotFoundError(f"Result file not found: {filename}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_raw_sources() -> dict:
    if not os.path.isdir(RAW_DATA):
        return {}
    files = os.listdir(RAW_DATA)
    return {
        "shapefiles": sorted(set(f for f in files if f.endswith(".shp"))),
        "csv":        sorted(f for f in files if f.endswith(".csv")),
        "tif":        sorted(f for f in files if f.endswith(".tif")),
        "defaults":   DEFAULT_SOURCES,
    }
