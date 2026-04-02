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

import logging
import os
import shutil

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


# ─── Preprocessing pipeline ───────────────────────────────────────────────────

def preprocess_all() -> None:
    """
    One-time preprocessing: converts all raw datasets into normalised
    score rasters (1–10 scale) saved in data/preprocessed/.

    Expected runtime: 15–40 minutes on a modern workstation for the full
    5 m resolution BLU.tif extent.
    """
    import arcpy
    from arcpy import sa as sa

    logger.info("=== Starting EV Siting Preprocessing ===")
    os.makedirs(PREPROCESSED, exist_ok=True)

    arcpy.CheckOutExtension("Spatial")
    _setup_env(BLU_TIF)

    try:
        # ── Step 1: Population density (persons / km²) from LSUG polygons ────
        logger.info("[1/6] Population density …")
        lsug_work = os.path.join(PREPROCESSED, "lsug_work.shp")
        if not arcpy.Exists(lsug_work):
            arcpy.conversion.FeatureClassToFeatureClass(
                LSUG_SHP, PREPROCESSED, "lsug_work.shp"
            )
        existing_fields = [f.name for f in arcpy.ListFields(lsug_work)]
        if "POP_DENS" not in existing_fields:
            arcpy.management.AddField(lsug_work, "POP_DENS", "DOUBLE")
            # !shape.area! returns area in m² (EPSG:2326 is metric) → divide by 1e6 for km²
            arcpy.management.CalculateField(
                lsug_work, "POP_DENS",
                "(!t_pop! / (!shape.area! / 1000000.0)) if !shape.area! > 0 else 0",
                "PYTHON3",
            )
        # Save raw raster to a temp path first to avoid file-lock when overwriting
        pop_raw = os.path.join(PREPROCESSED, "pop_raw.tif")
        arcpy.conversion.PolygonToRaster(
            lsug_work, "POP_DENS", pop_raw, "CELL_CENTER", "NONE", BLU_TIF
        )
        pop_score = _normalize_raster(sa.Raster(pop_raw), high_is_better=True)
        pop_score.save(OUT_POP)
        arcpy.management.Delete(pop_raw)
        logger.info("  → Population density done.")

        # ── Step 2: POI density (Kernel Density from GeoCom CSV) ──────────────
        logger.info("[2/6] POI density …")
        sr_2326 = arcpy.SpatialReference(2326)
        poi_lyr = "geocom_xy_lyr"
        if arcpy.Exists(poi_lyr):
            arcpy.management.Delete(poi_lyr)
        arcpy.management.MakeXYEventLayer(
            GEOCOM_CSV, "EASTING", "NORTHING", poi_lyr, sr_2326
        )
        ref = sa.Raster(BLU_TIF)
        cell_px = ref.meanCellWidth          # native resolution of BLU.tif (~5 m)
        search_radius = 500                  # 500 m bandwidth appropriate for HK urban scale
        poi_density = sa.KernelDensity(poi_lyr, "NONE", cell_px, search_radius)
        poi_score = _normalize_raster(poi_density, high_is_better=True)
        poi_score.save(OUT_POI)
        logger.info("  → POI density done.")

        # ── Step 3: Road accessibility (Euclidean distance to CENTERLINE) ─────
        logger.info("[3/6] Road accessibility …")
        # arcpy path parser treats ".gdb" anywhere in a path as a file geodatabase,
        # so all arcpy tools (including FeatureClassToFeatureClass) reject the raw path.
        # Use shutil to copy the shapefile components to a clean name with plain Python.
        centerline_clean = os.path.join(PREPROCESSED, "centerline_work.shp")
        if not os.path.exists(centerline_clean):
            _shutil_copy_shapefile(CENTERLINE_SHP, centerline_clean)
        arcpy.env.mask = ""
        road_dist = sa.EucDistance(centerline_clean)
        arcpy.env.mask = BLU_TIF
        # Closer to road = higher score → high_is_better=False
        road_score = _normalize_raster(road_dist, high_is_better=False)
        road_score.save(OUT_ROAD)
        logger.info("  → Road accessibility done.")

        # ── Step 4: EV competition (distance from existing chargers) ──────────
        logger.info("[4/6] EV competition distance …")
        # download_20260401_1622_converted.shp has no .gdb issue so use directly
        arcpy.env.mask = ""
        ev_dist = sa.EucDistance(EV_SHP)
        arcpy.env.mask = BLU_TIF
        # Farther from existing chargers = less competition = higher score
        ev_score = _normalize_raster(ev_dist, high_is_better=True)
        ev_score.save(OUT_EV)
        logger.info("  → EV competition done.")

        # ── Step 5: Slope suitability ─────────────────────────────────────────
        logger.info("[5/6] Slope suitability …")
        slope_r = sa.Raster(SLOPE_TIF)
        # Lower slope = more suitable for infrastructure
        slope_score = _normalize_raster(slope_r, high_is_better=False)
        slope_score.save(OUT_SLOPE)
        logger.info("  → Slope done.")

        # ── Step 6: Land-use score + binary mask from BLU.tif ─────────────────
        logger.info("[6/6] Land-use reclassification …")
        # Score mapping based on docs/landuse_code.txt
        remap = sa.RemapValue([
            [1,  6],         # Private Residential
            [2,  5],         # Public Residential
            [3,  3],         # Rural Settlement
            [11, 10],        # Commercial/Business & Office ← highest suitability
            [21, 4],         # Industrial Land
            [22, 4],         # Industrial Estates / Science Parks
            [23, 3],         # Warehouse and Open Storage
            [31, 7],         # Government, Institutional & Community
            [32, 6],         # Open Space and Recreation
            [41, 7],         # Roads and Transport Facilities
            [42, 5],         # Railways
            [43, 4],         # Airport
            [44, 4],         # Port Facilities
            [51, 2],         # Cemeteries / Funeral Facilities
            [52, 5],         # Utilities
            [53, 6],         # Vacant Land / Construction in Progress (opportunity)
            [54, 3],         # Others
            [61, 2],         # Agricultural Land
            [62, 2],         # Fish Ponds / Gei Wais
            # Restricted → NODATA (excluded from siting)
            [71, "NODATA"],  # Woodland
            [72, "NODATA"],  # Shrubland
            [73, "NODATA"],  # Grassland
            [74, "NODATA"],  # Mangrove / Swamp
            [83, "NODATA"],  # Rocky Shore
            [91, "NODATA"],  # Reservoirs
            [92, "NODATA"],  # Streams and Nullahs
        ])
        landuse_score = sa.Reclassify(BLU_TIF, "VALUE", remap, "NODATA")
        landuse_score.save(OUT_LANDUSE)

        # Binary mask: 1 = buildable, 0 = restricted/outside study area
        mask_r = sa.Con(sa.IsNull(landuse_score), 0, 1)
        mask_r.save(OUT_MASK)
        logger.info("  → Land-use done.")

    finally:
        arcpy.CheckInExtension("Spatial")

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

        return {"type": "FeatureCollection", "features": features}

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
