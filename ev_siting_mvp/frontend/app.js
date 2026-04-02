/**
 * app.js – HK EV Charging Site Selection Frontend
 *
 * Responsibilities:
 *  - Initialise Leaflet map centred on Hong Kong
 *  - Poll /api/status to track preprocessing progress
 *  - POST /api/preprocess to start the one-time data pipeline
 *  - POST /api/siting with normalised weights → render GeoJSON results
 */

'use strict';

const API_BASE = 'http://localhost:8000';

// Rank-badge colour palette (index = rank-1)
const RANK_COLOURS = [
  '#ef4444', // 1 – red
  '#f97316', // 2 – orange
  '#eab308', // 3 – yellow
  '#22c55e', // 4 – green
  '#3b82f6', // 5 – blue
  '#8b5cf6', // 6 – violet
  '#ec4899', // 7 – pink
  '#14b8a6', // 8 – teal
  '#f59e0b', // 9 – amber
  '#6366f1', // 10 – indigo
];

// ─── Leaflet map ──────────────────────────────────────────────────────────────

let map;
let siteLayer;   // LayerGroup for candidate site markers

function initMap() {
  map = L.map('map', { zoomControl: true }).setView([22.3193, 114.1694], 11);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  siteLayer = L.layerGroup().addTo(map);
}

// ─── Weight slider management ─────────────────────────────────────────────────

/**
 * Collect raw slider values, return {factor: normalised_weight, …}
 * where all weights sum to 1.0.
 */
function collectWeights() {
  const raw = {};
  let total = 0;
  document.querySelectorAll('.slider-row').forEach(row => {
    const factor = row.dataset.factor;
    const val    = parseFloat(row.querySelector('.weight-slider').value);
    raw[factor]  = val;
    total       += val;
  });

  const out = {};
  const denom = total > 0 ? total : 1;
  for (const [k, v] of Object.entries(raw)) out[k] = v / denom;
  return out;
}

/** Refresh the displayed raw value and normalised % for every slider. */
function refreshSliderLabels() {
  const weights = collectWeights();
  document.querySelectorAll('.slider-row').forEach(row => {
    const factor   = row.dataset.factor;
    const rawVal   = parseFloat(row.querySelector('.weight-slider').value);
    row.querySelector('.factor-raw').textContent = rawVal.toFixed(1);
    row.querySelector('.factor-pct').textContent =
      `${(weights[factor] * 100).toFixed(0)}%`;
  });
}

// ─── Preprocessing status ─────────────────────────────────────────────────────

let pollTimer = null;

async function fetchStatus() {
  try {
    const res  = await fetch(`${API_BASE}/api/status`);
    const data = await res.json();
    renderStatusPanel(data);
    if (data.all_ready) stopPolling();
    return data;
  } catch {
    setStatusBanner('error', 'Cannot reach backend at ' + API_BASE);
    return null;
  }
}

function renderStatusPanel(data) {
  const itemsEl  = document.getElementById('status-items');
  const runBtn   = document.getElementById('run-btn');
  const ppBtn    = document.getElementById('preprocess-btn');

  // Build per-raster checklist
  const lines = Object.entries(data)
    .filter(([k]) => k !== 'all_ready')
    .map(([label, done]) =>
      `<div class="flex items-center gap-1.5 text-xs leading-5">
        <span>${done ? '✅' : '⏳'}</span>
        <span class="${done ? 'text-gray-500' : 'text-amber-700'}">${label}</span>
      </div>`
    ).join('');
  itemsEl.innerHTML = lines;

  if (data.all_ready) {
    setStatusBanner('ok', 'All data ready — run analysis below.');
    runBtn.disabled = false;
    ppBtn.textContent = 'Re-preprocess Data';
    ppBtn.disabled    = false;
  } else {
    runBtn.disabled = true;
  }
}

function setStatusBanner(type, message) {
  const banner  = document.getElementById('status-banner');
  const textEl  = document.getElementById('status-text');
  const classes = {
    ok:      'bg-emerald-50 border-emerald-300',
    warn:    'bg-amber-50  border-amber-300',
    running: 'bg-sky-50    border-sky-300',
    error:   'bg-red-50    border-red-300',
  };
  const textColour = {
    ok:      'text-emerald-700',
    warn:    'text-amber-700',
    running: 'text-sky-700',
    error:   'text-red-700',
  };
  banner.className =
    `rounded-xl border px-3 py-2 mb-2 text-sm transition-all duration-500 ${classes[type] ?? classes.warn}`;
  textEl.className = `font-medium text-xs mb-1 ${textColour[type] ?? textColour.warn}`;
  textEl.textContent = message;
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(fetchStatus, 4000);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// ─── Trigger preprocessing ────────────────────────────────────────────────────

async function triggerPreprocess() {
  const btn = document.getElementById('preprocess-btn');
  btn.disabled    = true;
  btn.textContent = 'Starting…';

  try {
    const res  = await fetch(`${API_BASE}/api/preprocess`, { method: 'POST' });
    const data = await res.json();

    if (data.status === 'started') {
      setStatusBanner('running', '⏳ Preprocessing started – this takes 15–30 min. Status updates every 4 s.');
      btn.textContent = 'Processing… (check status)';
      startPolling();
    } else if (data.status === 'running') {
      setStatusBanner('running', 'Already running – polling for updates.');
      btn.textContent = 'Already running…';
      startPolling();
    } else {
      btn.disabled    = false;
      btn.textContent = 'Preprocess Data';
    }
  } catch (err) {
    setStatusBanner('error', 'Failed to start preprocessing: ' + err.message);
    btn.disabled    = false;
    btn.textContent = 'Preprocess Data';
  }
}

// ─── Run suitability analysis ─────────────────────────────────────────────────

async function runAnalysis() {
  const runBtn  = document.getElementById('run-btn');
  const spinner = document.getElementById('spinner');
  const label   = document.getElementById('run-label');

  runBtn.disabled    = true;
  spinner.classList.remove('hidden');
  label.textContent  = 'Analysing…';

  try {
    const weights  = collectWeights();
    const numSites = Math.max(1, Math.min(20, parseInt(document.getElementById('num-sites').value, 10) || 5));

    const res = await fetch(`${API_BASE}/api/siting`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ weights, num_sites: numSites }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Server error');
    }

    const geojson = await res.json();
    renderResults(geojson);

  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  } finally {
    runBtn.disabled   = false;
    spinner.classList.add('hidden');
    label.textContent = 'Run Analysis';
  }
}

// ─── Map rendering ────────────────────────────────────────────────────────────

function renderResults(geojson) {
  siteLayer.clearLayers();
  document.getElementById('results-panel').classList.add('hidden');

  const features = geojson.features || [];
  if (features.length === 0) {
    showToast('No suitable sites found – try adjusting weights.', 'warn');
    return;
  }

  const bounds = [];

  features.forEach(feature => {
    const [lng, lat]  = feature.geometry.coordinates;
    const { rank, score } = feature.properties;
    const colour = RANK_COLOURS[(rank - 1) % RANK_COLOURS.length];

    // Numbered div-icon
    const icon = L.divIcon({
      html: `<div style="
               background:${colour};
               color:#fff;
               border-radius:50%;
               width:30px;height:30px;
               display:flex;align-items:center;justify-content:center;
               font-weight:700;font-size:13px;
               border:2.5px solid #fff;
               box-shadow:0 2px 6px rgba(0,0,0,.35);">
               ${rank}
             </div>`,
      iconSize:   [30, 30],
      iconAnchor: [15, 15],
      className:  '',
    });

    const popup = `
      <div style="font-family:system-ui,sans-serif;min-width:160px;">
        <div style="font-size:15px;font-weight:700;color:${colour};margin-bottom:4px;">
          Candidate Site #${rank}
        </div>
        <div style="font-size:13px;color:#374151;">
          Suitability score:
          <strong style="color:#059669;">${score.toFixed(3)}</strong>
        </div>
        <div style="font-size:11px;color:#9ca3af;margin-top:4px;">
          ${lat.toFixed(5)}°N, ${lng.toFixed(5)}°E
        </div>
      </div>`;

    L.marker([lat, lng], { icon })
      .bindPopup(popup)
      .addTo(siteLayer);

    bounds.push([lat, lng]);
  });

  if (bounds.length > 0) {
    map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
  }

  // Populate sidebar results list
  const listEl   = document.getElementById('results-list');
  const countEl  = document.getElementById('results-count');
  countEl.textContent = `${features.length} site${features.length !== 1 ? 's' : ''}`;

  listEl.innerHTML = features.map(f => {
    const [lng, lat] = f.geometry.coordinates;
    const colour = RANK_COLOURS[(f.properties.rank - 1) % RANK_COLOURS.length];
    return `
      <button class="w-full text-left border border-gray-200 rounded-lg px-3 py-2
                     hover:bg-blue-50 transition-colors text-sm"
              onclick="map.setView([${lat}, ${lng}], 15)">
        <div class="flex items-center justify-between">
          <span class="inline-flex items-center justify-center w-6 h-6 rounded-full text-white text-xs font-bold"
                style="background:${colour};">${f.properties.rank}</span>
          <span class="font-semibold text-emerald-600">${f.properties.score.toFixed(3)}</span>
        </div>
        <div class="text-gray-400 text-xs mt-0.5">
          ${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E
        </div>
      </button>`;
  }).join('');

  document.getElementById('results-panel').classList.remove('hidden');
}

// ─── Toast / notification helper ─────────────────────────────────────────────

function showToast(message, type = 'info') {
  const colours = {
    info:  'bg-gray-700 text-white',
    warn:  'bg-amber-500 text-white',
    error: 'bg-red-600 text-white',
    ok:    'bg-emerald-500 text-white',
  };
  const toast = document.createElement('div');
  toast.className =
    `fixed bottom-6 left-1/2 -translate-x-1/2 px-5 py-3 rounded-xl shadow-xl
     text-sm font-medium z-[9999] transition-opacity duration-500
     ${colours[type] ?? colours.info}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 500);
  }, 4500);
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initMap();

  // Attach slider listeners
  document.querySelectorAll('.weight-slider').forEach(slider => {
    slider.addEventListener('input', refreshSliderLabels);
  });
  refreshSliderLabels();

  // Button handlers
  document.getElementById('preprocess-btn').addEventListener('click', triggerPreprocess);
  document.getElementById('run-btn').addEventListener('click', runAnalysis);

  // Initial status check
  fetchStatus();
});
