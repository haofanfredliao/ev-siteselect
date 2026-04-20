import DataStatusBanner from './DataStatusBanner';
import FactorModuleList from './FactorModuleList';
import ValidateAllButton from './ValidateAllButton';
import RunAnalysisSection from './RunAnalysisSection';
import ResultsList from './ResultsList';
import ResultHistory from './ResultHistory';
import DistrictSelector from './DistrictSelector';
import { SCENARIOS, FACTOR_DEFS } from '../utils/constants';

// One-click scenario preset bar
function ScenarioPresets({ factors, onUpdate }) {
  const applyScenario = (scenario) => {
    factors.forEach(f => {
      if (scenario.weights[f.key] !== undefined) {
        onUpdate(f.key, { weight: scenario.weights[f.key] });
      }
    });
  };

  return (
    <div className="mb-2">
      <p className="text-xs text-gray-400 mb-1.5">Quick presets</p>
      <div className="flex gap-1.5 flex-wrap">
        {SCENARIOS.map(s => (
          <button
            key={s.id}
            onClick={() => applyScenario(s)}
            title={Object.entries(s.weights)
              .filter(([k]) => FACTOR_DEFS[k])
              .map(([k, w]) => `${FACTOR_DEFS[k].label}: ${(w * 10).toFixed(0)}%`)
              .join('\n')}
            className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-200
                       bg-gray-50 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700
                       text-gray-600 transition-colors font-medium"
          >
            <span>{s.emoji}</span>
            <span>{s.labelEn}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function AnalysisTab({
  factors, sources, allReady, statusError,
  onUpdateFactor, onRemoveFactor, onAddFactor,
  onStatusUpdate, collectWeights, onResults, geojson, onFlyTo,
  selectedDistricts, onDistrictsChange,
  activeLayer, onLayerChange,
}) {
  return (
    <div className="flex flex-col gap-3">
      {/* Data status */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
          Data Status
        </h2>
        <DataStatusBanner allReady={allReady} error={statusError} />
      </section>

      {/* Study area selector */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
          Study Area
        </h2>
        <DistrictSelector selected={selectedDistricts} onChange={onDistrictsChange} />
      </section>

      <hr className="border-gray-100" />

      {/* Factor modules */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
          Factor Weights
        </h2>
        <ScenarioPresets factors={factors} onUpdate={onUpdateFactor} />
        <FactorModuleList
          factors={factors}
          sources={sources}
          onUpdate={onUpdateFactor}
          onRemove={onRemoveFactor}
          onAdd={onAddFactor}
          activeLayer={activeLayer}
          onLayerChange={onLayerChange}
        />
        <ValidateAllButton onStatusUpdate={onStatusUpdate} />
      </section>

      <hr className="border-gray-100" />

      {/* Run analysis */}
      <section>
        <RunAnalysisSection
          allReady={allReady}
          collectWeights={collectWeights}
          onResults={onResults}
          studyArea={selectedDistricts}
          onLayerChange={onLayerChange}
        />
        <ResultHistory onLoadResult={onResults} />
      </section>

      {/* Results list */}
      <ResultsList geojson={geojson} onFlyTo={onFlyTo} />
    </div>
  );
}
