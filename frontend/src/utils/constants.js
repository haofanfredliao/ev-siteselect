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
