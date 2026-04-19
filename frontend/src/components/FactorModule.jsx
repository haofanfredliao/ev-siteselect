import { useState } from 'react';
import { FACTOR_DEFS } from '../utils/constants';
import { triggerPreprocessFactor } from '../utils/api';

export default function FactorModule({ factor, sources, totalWeight, onUpdate, onRemove }) {
  const def = FACTOR_DEFS[factor.key] || { label: factor.key, emoji: '📊', description: '' };
  const [preprocessing, setPreprocessing] = useState(false);

  const pct = totalWeight > 0 ? ((factor.weight / totalWeight) * 100).toFixed(0) : 0;

  const handlePreprocess = async () => {
    setPreprocessing(true);
    onUpdate(factor.key, { status: 'pending' });
    try {
      await triggerPreprocessFactor(factor.key, factor.source);
      onUpdate(factor.key, { status: 'ready' });
    } catch {
      onUpdate(factor.key, { status: 'error' });
    } finally {
      setPreprocessing(false);
    }
  };

  const statusIcon = { ready: '✅', pending: '⏳', error: '❌', unknown: '❓' }[factor.status] || '❓';

  // Build dropdown options from available sources
  const relevantSources = sources || [];

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white relative group">
      {/* Header */}
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-sm font-medium text-gray-700">
          {def.emoji} {def.label} <span className="ml-1 text-xs">{statusIcon}</span>
        </span>
        <div className="flex gap-1 items-center">
          <span className="text-xs text-gray-400 w-5 text-right">{factor.weight.toFixed(1)}</span>
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
        type="range" min="0" max="10" step="0.5"
        value={factor.weight}
        onChange={e => onUpdate(factor.key, { weight: parseFloat(e.target.value) })}
        className="w-full h-1.5 accent-blue-600"
      />
      <p className="text-xs text-gray-400 mt-0.5">{def.description}</p>

      {/* Data source dropdown */}
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
          disabled={preprocessing}
          className="text-xs px-2 py-1 rounded bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-50 transition-colors whitespace-nowrap"
        >
          {preprocessing ? '⏳' : '▶'} Prep
        </button>
      </div>
    </div>
  );
}
