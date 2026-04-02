# PRD: Hong Kong EV Charging Station Siting MVP 

## 1. Project Overview

Build a Minimum Viable Product (MVP) for an EV Charging Station Site Selection Web App in Hong Kong. The application consists of a Python backend utilizing `arcpy` for spatial analysis (Suitability Modeling) and a lightweight HTML/JS frontend for user interaction and map visualization.

**Goal:** Allow users to adjust weights for different spatial factors on a web UI, send the weights to the backend, calculate a suitability raster using `arcpy`, extract the top NNN suitable locations, and display them on a web map.

## 2. Tech Stack

- **Backend:** Python 3 (ArcGIS Pro Clone Environment), `arcpy`, `FastAPI`, `uvicorn`.
- **Frontend:** HTML5, Vanilla JavaScript, Tailwind CSS (via CDN), Leaflet.js (via CDN).
- **Data Exchange:** JSON / GeoJSON.

## 3. Directory Structure

Please create the following directory structure and files:

```text
ev_siting_mvp/
├── data/
│   ├── preprocessed/          # Agent: Assume pre-calculated rasters exist here
│   │   ├── pop_density.tif    # Population density (1-10 score)
│   │   ├── poi_heat.tif       # POI kernel density (1-10 score)
│   │   ├── road_dist.tif      # Distance to roads (1-10 score)
│   │   ├── ev_dist.tif        # Distance to existing EV (1-10 score)
│   │   └── landuse_mask.tif   # Buildable area mask (1=buildable, 0=not)
├── backend/
│   ├── main.py                # FastAPI application entry point
│   ├── arcpy_engine.py        # ArcPy geoprocessing logic
│   └── requirements.txt       # fastapi, uvicorn
└── frontend/
    ├── index.html             # Main UI
    ├── app.js                 # Frontend logic and API calls
    └── style.css              # Custom styles (if needed beyond Tailwind)
```

## 4. Backend Requirements (FastAPI + ArcPy)

### 4.1 API Endpoint

- **Route:** `POST /api/siting`

- Input (JSON):

  ```json
  {
    "weights": {
      "population": 0.4,
      "poi": 0.3,
      "road_accessibility": 0.2,
      "existing_ev_competition": 0.1
    },
    "num_sites": 5
  }
  ```

- Output (GeoJSON):

  ```json
  {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [114.1694, 22.3193]},
        "properties": {"score": 9.5, "rank": 1}
      }
    ]
  }
  ```

### 4.2 ArcPy Logic (`backend/arcpy_engine.py`)

Agent must implement a function `run_suitability_model(weights: dict, num_sites: int) -> dict`:

1. **Environment Setup:** Set `arcpy.env.workspace` to the `data/preprocessed` folder. Set `arcpy.env.overwriteOutput = True`. Check out the Spatial Analyst extension (`arcpy.CheckOutExtension("Spatial")`).
2. **Raster Math:** Use `arcpy.sa.Raster` to load the 4 factor TIFFs and 1 mask TIFF.
3. **Weighted Overlay:** Calculate the final score:
    `final_raster = (pop * w1 + poi * w2 + road * w3 + ev * w4) * mask`
4. Extract Top Sites:
   - Find the maximum value in `final_raster`.
   - Use `arcpy.sa.Con` to extract pixels close to the maximum value (e.g., top 5%).
   - Convert the extracted raster to points using `arcpy.conversion.RasterToPoint`.
   - Sort the points by grid code (score) descending, take the top `num_sites`.
5. **Coordinate Conversion:** Ensure the output points are projected to WGS84 (EPSG:4326) so Leaflet can render them. (Use `arcpy.management.Project` if the source is in HK 1980 Grid EPSG:2326).
6. **Format Output:** Convert the top points into a standard GeoJSON dictionary and return it.

## 5. Frontend Requirements (HTML/JS)

### 5.1 UI Layout (`frontend/index.html`)

- Use Tailwind CSS for styling.
- Left Sidebar (30% width):
  - Title: "HK EV Siting MVP".
  - 4 Range Sliders (0 to 1, step 0.1) for the weights: Population, POI, Road, EV Competition.
  - Number input for `num_sites` (default 5).
  - A "Run Analysis" button.
  - A loading spinner (hidden by default).
- Right Map Area (70% width):
  - A `div` with `id="map"` taking full height.

### 5.2 Map & Logic (`frontend/app.js`)

- Initialize a Leaflet map centered on Hong Kong (Lat: 22.3193, Lng: 114.1694), Zoom level 11.
- Use OpenStreetMap as the base layer.
- Attach an event listener to the "Run Analysis" button.
- On click:
  1. Show loading spinner.
  2. Read values from sliders and normalize them so they sum to 1.0.
  3. `fetch()` POST to `http://localhost:8000/api/siting`.
  4. On response, parse the GeoJSON.
  5. Clear existing markers on the map.
  6. Add new markers from the GeoJSON to the map. Add a popup to each marker showing its "Rank" and "Score".
  7. Hide loading spinner.

## 6. Implementation Steps for Agent

1. **Step 1:** Create the directory structure and placeholder files.
2. **Step 2:** Write the `backend/requirements.txt` and `backend/main.py` (FastAPI setup with CORS middleware enabled).
3. **Step 3:** Implement the `backend/arcpy_engine.py`. *Note for Agent: Since you cannot run arcpy in your sandbox, write the code assuming a standard ArcGIS Pro Python 3 environment. Add robust error handling and mock data generation logic (e.g., creating dummy TIFFs using `numpy` and `arcpy.NumPyArrayToRaster`) if the actual TIFFs are missing, so the API can still be tested.*
4. **Step 4:** Write `frontend/index.html` with Tailwind and Leaflet CDN links.
5. **Step 5:** Write `frontend/app.js` to handle the UI state, API request, and map rendering.
6. **Step 6:** Review code for integration issues (e.g., CORS, correct JSON payload structure).

**Agent, please acknowledge these requirements and begin by generating the code for Step 1 and Step 2.**