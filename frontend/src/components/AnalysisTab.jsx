import DataStatusBanner from './DataStatusBanner';
import FactorModuleList from './FactorModuleList';
import ValidateAllButton from './ValidateAllButton';
import RunAnalysisSection from './RunAnalysisSection';
import ResultsList from './ResultsList';
import ResultHistory from './ResultHistory';

export default function AnalysisTab({
  factors, sources, allReady, statusError,
  onUpdateFactor, onRemoveFactor, onAddFactor,
  onStatusUpdate, collectWeights, onResults, geojson, onFlyTo,
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

      {/* Factor modules */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
          Factor Weights
        </h2>
        <FactorModuleList
          factors={factors}
          sources={sources}
          onUpdate={onUpdateFactor}
          onRemove={onRemoveFactor}
          onAdd={onAddFactor}
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
        />
        <ResultHistory onLoadResult={onResults} />
      </section>

      {/* Results list */}
      <ResultsList geojson={geojson} onFlyTo={onFlyTo} />
    </div>
  );
}
