import { useState, useRef, useCallback } from 'react';
import AnalysisTab from './AnalysisTab';
import AIChatTab from './AIChatTab';

const TABS = [
  { id: 'analysis', label: '📊 Analysis' },
  { id: 'ai',       label: '🤖 AI Assistant' },
];

export default function Sidebar({
  factors, sources, allReady, statusError,
  onUpdateFactor, onRemoveFactor, onAddFactor,
  onStatusUpdate, collectWeights, onResults, geojson, onFlyTo,
  selectedDistricts, onDistrictsChange,
  activeLayer, onLayerChange,
}) {
  const [activeTab, setActiveTab] = useState('analysis');
  const [width, setWidth] = useState(320);
  const dragging = useRef(false);

  const onMouseDown = useCallback((e) => {
    e.preventDefault();
    dragging.current = true;
    const startX = e.clientX;
    const startW = width;
    const onMove = (ev) => {
      if (!dragging.current) return;
      setWidth(Math.max(260, Math.min(600, startW + ev.clientX - startX)));
    };
    const onUp = () => { dragging.current = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [width]);

  return (
    <aside style={{ width }} className="flex-shrink-0 bg-white shadow-2xl z-10 flex flex-col h-screen relative">
      {/* Header */}
      <div className="bg-gradient-to-br from-blue-700 to-emerald-600 px-5 py-4 text-white flex-shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">⚡</span>
          <h1 className="text-lg font-bold leading-tight">HK EV Charging<br/>Site Selection</h1>
        </div>
        <p className="text-xs text-white/70">Powered by ArcPy · FastAPI · React</p>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 flex-shrink-0">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex-1 text-xs font-medium py-2 transition-colors ${
              activeTab === t.id
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >{t.label}</button>
        ))}
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {activeTab === 'analysis' ? (
          <AnalysisTab
            factors={factors}
            sources={sources}
            allReady={allReady}
            statusError={statusError}
            onUpdateFactor={onUpdateFactor}
            onRemoveFactor={onRemoveFactor}
            onAddFactor={onAddFactor}
            onStatusUpdate={onStatusUpdate}
            collectWeights={collectWeights}
            onResults={onResults}
            geojson={geojson}
            onFlyTo={onFlyTo}
            selectedDistricts={selectedDistricts}
            onDistrictsChange={onDistrictsChange}
            activeLayer={activeLayer}
            onLayerChange={onLayerChange}
          />
        ) : (
          <AIChatTab />
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-gray-100 text-center flex-shrink-0">
        <p className="text-xs text-gray-400">HK EV Siting · © 2026</p>
      </div>

      {/* Resize handle */}
      <div
        onMouseDown={onMouseDown}
        className="absolute top-0 right-0 w-1.5 h-full cursor-col-resize hover:bg-blue-400/40 active:bg-blue-500/50 transition-colors"
      />
    </aside>
  );
}
