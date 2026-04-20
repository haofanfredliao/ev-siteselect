const API_BASE = '/api';

export async function fetchStatus() {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

export async function triggerPreprocessAll() {
  const res = await fetch(`${API_BASE}/preprocess`, { method: 'POST' });
  return res.json();
}

export async function triggerPreprocessFactor(factorKey, source) {
  const res = await fetch(`${API_BASE}/preprocess/${factorKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Preprocessing failed');
  }
  return res.json();
}

export async function fetchRawSources() {
  const res = await fetch(`${API_BASE}/raw-sources`);
  if (!res.ok) throw new Error('Failed to fetch raw sources');
  return res.json();
}

export async function runSiting(weights, numSites, studyArea = []) {
  const res = await fetch(`${API_BASE}/siting`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weights, num_sites: numSites, study_area: studyArea }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Analysis failed');
  }
  return res.json();
}

export async function fetchResults() {
  const res = await fetch(`${API_BASE}/results`);
  if (!res.ok) throw new Error('Failed to fetch results');
  return res.json();
}

export async function fetchResultFile(filename) {
  const res = await fetch(`${API_BASE}/results/${encodeURIComponent(filename)}`);
  if (!res.ok) throw new Error('Failed to fetch result');
  return res.json();
}

export function streetViewUrl(lat, lng) {
  return `${API_BASE}/streetview?lat=${lat}&lng=${lng}`;
}

export async function fetchDistrictGeoJSON() {
  const res = await fetch(`${API_BASE}/districts/geojson`);
  if (!res.ok) throw new Error('Failed to fetch district GeoJSON');
  return res.json();
}

export async function fetchRasterLayer(name) {
  const res = await fetch(`${API_BASE}/layer/raster/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error(`Raster layer not available: ${name}`);
  return res.json();  // { png_base64, bounds, name }
}

export async function fetchVectorLayer(name) {
  const res = await fetch(`${API_BASE}/layer/vector/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error(`Vector layer not available: ${name}`);
  return res.json();  // GeoJSON FeatureCollection
}

export async function sendAiChat(message, history) {
  const res = await fetch(`${API_BASE}/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'AI chat failed');
  }
  return res.json();
}
