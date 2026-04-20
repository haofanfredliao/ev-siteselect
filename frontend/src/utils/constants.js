// All 18 Hong Kong districts (NAME_EN values from AdminArea.shp)
export const ALL_DISTRICTS = [
  'Central and Western District',
  'Eastern District',
  'Islands District',
  'Kowloon City District',
  'Kwai Tsing District',
  'Kwun Tong District',
  'North District',
  'Sai Kung District',
  'Sha Tin District',
  'Sham Shui Po District',
  'Southern District',
  'Tai Po District',
  'Tsuen Wan District',
  'Tuen Mun District',
  'Wan Chai District',
  'Wong Tai Sin District',
  'Yau Tsim Mong District',
  'Yuen Long District',
];

// Basemap definitions
export const BASEMAPS = [
  {
    id:    'osm',
    label: 'OpenStreetMap',
    url:   'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  },
  {
    id:    'esri_topo',
    label: 'Esri Topographic',
    url:   'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC',
    maxZoom: 19,
  },
  {
    id:    'esri_light',
    label: 'Esri Light Gray',
    url:   'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    maxZoom: 16,
  },
];

// Per-factor layer names for Raw (vector) and Score (raster) overlays
export const FACTOR_LAYERS = {
  population:         { raw: 'population',  score: 'pop_density'   },
  poi:                { raw: 'poi_sample',  score: 'poi_heat'      },
  road_accessibility: { raw: null,          score: 'road_dist'     },
  ev_competition:     { raw: 'ev_charger',  score: 'ev_dist'       },
  slope:              { raw: null,          score: 'slope_score'   },
  landuse:            { raw: null,          score: 'landuse_score' },
};

// Rank-badge colour palette (index = rank - 1)
export const RANK_COLOURS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b', '#6366f1',
];

export const FACTOR_DEFS = {
  population:        { label: 'Population Density',  emoji: '👥', description: 'Higher density → more customers' },
  poi:               { label: 'POI Density',         emoji: '📍', description: 'Commercial activity footfall' },
  road_accessibility:{ label: 'Road Accessibility',  emoji: '🛣️', description: 'Proximity to road centre-lines' },
  ev_competition:    { label: 'EV Competition',      emoji: '⚡', description: 'Distance from existing chargers' },
  slope:             { label: 'Slope (flat = better)',emoji: '⛰️', description: 'Lower slope → easier installation' },
  landuse:           { label: 'Land Use',            emoji: '🏢', description: 'Commercial scored highest; natural excluded' },
};

// Map from factor key to expected preprocessed raster label returned by /api/status
export const FACTOR_STATUS_KEY = {
  population:         'Population Density',
  poi:                'POI Density',
  road_accessibility: 'Road Accessibility',
  ev_competition:     'EV Competition',
  slope:              'Slope Suitability',
  landuse:            'Land Use Score',
};

// C1=road_accessibility, C2=population, C3=ev_competition, C4=landuse, C5=slope, C6=poi
// Weights are the % influence values divided by 10 to fit the 0–10 slider range.
export const SCENARIOS = [
  {
    id: 'equal',
    label: '等权重',
    labelEn: 'Equal',
    emoji: '⚖️',
    weights: {
      road_accessibility: 17,
      population:         17,
      ev_competition:     17,
      landuse:            16,
      slope:              16,
      poi:                17,
    },
  },
  {
    id: 'transport',
    label: '交通优先',
    labelEn: 'Transport',
    emoji: '🚗',
    weights: {
      road_accessibility: 30,
      population:         10,
      ev_competition:     10,
      landuse:            7,
      slope:              5,
      poi:                38,
    },
  },
  {
    id: 'equity',
    label: '公平覆盖',
    labelEn: 'Equity',
    emoji: '🏙️',
    weights: {
      road_accessibility: 10,
      population:         25,
      ev_competition:     30,
      landuse:            8,
      slope:              5,
      poi:                22,
    },
  },
];
