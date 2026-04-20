import { useState } from 'react';
import { runSiting } from '../utils/api';

export default function RunAnalysisSection({ allReady, collectWeights, onResults, studyArea = [], onLayerChange }) {
  const [numSites, setNumSites] = useState(5);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [showHeatmap, setShowHeatmap] = useState(false);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const weights = collectWeights();
      const geojson = await runSiting(weights, numSites, studyArea);
      onResults(geojson);
      if (showHeatmap) {
        onLayerChange?.({ type: 'raster', name: 'final_score' });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-2">
      <div>
        <label className="text-xs font-semibold text-gray-400 uppercase tracking-widest block mb-1">
          Results Count
        </label>
        <input
          type="number" value={numSites} min={1} max={20}
          onChange={e => setNumSites(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Study area summary */}
      {studyArea.length > 0 && studyArea.length < 18 && (
        <p className="text-xs text-blue-600">
          Area: {studyArea.length} district{studyArea.length > 1 ? 's' : ''} selected
        </p>
      )}

      <button
        onClick={handleRun}
        disabled={!allReady || running}
        className="w-full py-2.5 text-sm font-semibold rounded-xl transition-all duration-200
                   bg-blue-600 hover:bg-blue-700 text-white
                   disabled:bg-gray-300 disabled:cursor-not-allowed
                   flex items-center justify-center gap-2"
      >
        {running ? (
          <>
            <svg className="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            Analysing…
          </>
        ) : 'Run Analysis'}
      </button>

      {/* Heatmap toggle */}
      <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={showHeatmap}
          onChange={e => {
            setShowHeatmap(e.target.checked);
            if (!e.target.checked) onLayerChange?.(null);
          }}
          className="accent-blue-600"
        />
        Show suitability heatmap after analysis
      </label>

      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

