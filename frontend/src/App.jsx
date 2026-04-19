import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';
import useFactors from './hooks/useFactors';
import { fetchStatus, fetchRawSources } from './utils/api';

export default function App() {
  const {
    factors, updateFactor, addFactor, removeFactor,
    setWeightsBatch, collectWeights, syncStatus,
  } = useFactors();

  const [geojson, setGeojson] = useState(null);
  const [allReady, setAllReady] = useState(false);
  const [statusError, setStatusError] = useState(null);
  const [sources, setSources] = useState({});     // { factorKey: [file1, file2, ...] }
  const flyToRef = useRef(null);

  // Status polling
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const data = await fetchStatus();
        if (!active) return;
        syncStatus(data);
        setAllReady(!!data.all_ready);
        setStatusError(null);
      } catch {
        if (active) setStatusError('Cannot reach backend');
      }
    };
    poll();
    const id = setInterval(poll, 4000);
    return () => { active = false; clearInterval(id); };
  }, [syncStatus]);

  // Load raw data sources once, transform to per-factor arrays
  useEffect(() => {
    fetchRawSources().then(raw => {
      if (!raw || !raw.defaults) return;
      // Map each factor to the file list matching its default source type
      const mapped = {};
      for (const [key, defaultFile] of Object.entries(raw.defaults)) {
        const ext = defaultFile.split('.').pop().toLowerCase();
        if (ext === 'shp') mapped[key] = raw.shapefiles || [];
        else if (ext === 'csv') mapped[key] = raw.csv || [];
        else if (ext === 'tif') mapped[key] = raw.tif || [];
        else mapped[key] = [];
      }
      setSources(mapped);
    }).catch(() => {});
  }, []);

  const handleStatusUpdate = useCallback((data) => {
    syncStatus(data);
    setAllReady(!!data.all_ready);
  }, [syncStatus]);

  const handleFlyTo = useCallback((lat, lng) => {
    flyToRef.current?.(lat, lng);
  }, []);

  return (
    <div className="flex h-screen bg-gray-100 font-sans">
      <Sidebar
        factors={factors}
        sources={sources}
        allReady={allReady}
        statusError={statusError}
        onUpdateFactor={updateFactor}
        onRemoveFactor={removeFactor}
        onAddFactor={addFactor}
        onStatusUpdate={handleStatusUpdate}
        collectWeights={collectWeights}
        onResults={setGeojson}
        geojson={geojson}
        onFlyTo={handleFlyTo}
      />
      <main className="flex-1 relative">
        <MapView geojson={geojson} flyToRef={flyToRef} />
      </main>
    </div>
  );
}
