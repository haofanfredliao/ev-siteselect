import { useState, useEffect } from 'react';
import { FACTOR_DEFS, FACTOR_LAYERS } from '../utils/constants';
import { triggerPreprocessFactor } from '../utils/api';

export default function FactorModule({ factor, sources, totalWeight, onUpdate, onRemove, activeLayer, onLayerChange }) {
  const def = FACTOR_DEFS[factor.key] || { label: factor.key, emoji: '📊', description: '' };
  const layers = FACTOR_LAYERS[factor.key] || {};
  const [preprocessing, setPreprocessing] = useState(false);

  // Clear local preprocessing spinner once the backend confirms the raster is ready
  useEffect(() => {
    if (factor.status === 'ready' && preprocessing) {
      setPreprocessing(false);
    }
  }, [factor.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const pct = totalWeight > 0 ? ((factor.weight / totalWeight) * 100).toFixed(0) : 0;

  const handlePreprocess = async () => {
    setPreprocessing(true);
    onUpdate(factor.key, { status: 'running' });
    try {
      await triggerPreprocessFactor(factor.key, factor.source);
      // Do NOT set status: 'ready' here — let polling resolve the true state
    } catch {
      onUpdate(factor.key, { status: 'error' });
      setPreprocessing(false);
    }
    // Note: setPreprocessing(false) is handled by the useEffect above
  };

  // A factor is "busy" if either the local trigger is in flight or backend says it's running
  const isBusy = preprocessing || factor.status === 'running';

  const isActiveRaster = activeLayer?.type === 'raster' && activeLayer?.name === layers.score;
  const isActiveVector = activeLayer?.type === 'vector' && activeLayer?.name === layers.raw;

  const toggleLayer = (type, name) => {
    if (!name) return;
    const isActive = type === 'raster' ? isActiveRaster : isActiveVector;
    onLayerChange?.(isActive ? null : { type, name });
  };

  const statusIcon = {
    ready:   '✅',
    running: '⏳',
    error:   '❌',
    unknown: '❓',
  }[factor.status] || '❓';

  const relevantSources = sources || [];

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white relative group">
      {/* Header */}
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-sm font-medium text-gray-700">
          {def.emoji} {def.label} <span className="ml-1 text-xs">{statusIcon}</span>
        </span>
        <div className="flex gap-1 items-center">
          <span className="text-xs text-gray-400 w-7 text-right">{factor.weight}</span>
          <span className="text-xs font-semibold text-blue-600 w-9 text-right">{pct}%</span>
          <button
            onClick={() => onRemove(factor.key)}
            className="ml-1 text-gray-300 hover:text-red-500 text-xs font-bold transition-colors"
            title="Remove factor"
          >✕</button>
        </div>
      </div>

      {/* Weight slider */}
      <input
        type="range" min="0" max="100" step="1"
        value={factor.weight}
        onChange={e => onUpdate(factor.key, { weight: parseFloat(e.target.value) })}
        className="w-full h-1.5 accent-blue-600"
      />
      <p className="text-xs text-gray-400 mt-0.5">{def.description}</p>

      {/* Busy indicator */}
      {isBusy && (
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-amber-600">
          <svg className="w-3 h-3 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          Processing…
        </div>
      )}

      {/* Data source + action row */}
      <div className="mt-2 flex gap-1.5 items-center min-w-0">
        <select
          value={factor.source}
          onChange={e => onUpdate(factor.key, { source: e.target.value })}
          className="flex-1 min-w-0 text-xs border border-gray-200 rounded px-1.5 py-1 bg-gray-50 truncate focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">Default source</option>
          {relevantSources.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button
          onClick={handlePreprocess}
          disabled={isBusy}
          className="text-xs px-2 py-1 rounded bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-50 transition-colors whitespace-nowrap"
        >
          {isBusy ? '⏳' : '▶'} Prep
        </button>
      </div>

      {/* Layer toggle buttons */}
      <div className="mt-1.5 flex gap-1">
        {layers.raw && (
          <button
            onClick={() => toggleLayer('vector', layers.raw)}
            title="Show raw data layer"
            className={`text-xs px-2 py-0.5 rounded border transition-colors ${
              isActiveVector
                ? 'bg-emerald-600 text-white border-emerald-600'
                : 'border-gray-300 text-gray-500 hover:border-emerald-400 hover:text-emerald-600'
            }`}
          >📊 Raw</button>
        )}
        {layers.score && (
          <button
            onClick={() => toggleLayer('raster', layers.score)}
            disabled={factor.status !== 'ready'}
            title="Show score raster"
            className={`text-xs px-2 py-0.5 rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              isActiveRaster
                ? 'bg-blue-600 text-white border-blue-600'
                : 'border-gray-300 text-gray-500 hover:border-blue-400 hover:text-blue-600'
            }`}
          >🗺 Score</button>
        )}
      </div>
    </div>
  );
}


