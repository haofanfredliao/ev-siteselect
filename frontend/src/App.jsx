import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';
import useFactors from './hooks/useFactors';
import { fetchStatus, fetchRawSources, fetchDistrictGeoJSON, fetchRasterLayer, fetchVectorLayer } from './utils/api';
import { ALL_DISTRICTS } from './utils/constants';

export default function App() {
  const {
    factors, updateFactor, addFactor, removeFactor,
    setWeightsBatch, collectWeights, syncStatus,
  } = useFactors();

  const [geojson, setGeojson]               = useState(null);
  const [allReady, setAllReady]             = useState(false);
  const [statusError, setStatusError]       = useState(null);
  const [sources, setSources]               = useState({});
  const flyToRef = useRef(null);

  // District state
  const [selectedDistricts, setSelectedDistricts] = useState(ALL_DISTRICTS);
  const [districtGeoJSON, setDistrictGeoJSON]     = useState(null);

  // Layer overlay state
  const [activeLayer, setActiveLayer] = useState(null);  // {type:'raster'|'vector', name:str}
  const [layerData, setLayerData]     = useState(null);  // fetched layer payload

  // Basemap state
  const [basemap, setBasemap] = useState('osm');

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

  // Load raw data sources once
  useEffect(() => {
    fetchRawSources().then(raw => {
      if (!raw || !raw.defaults) return;
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

  // Load district boundaries once on mount
  useEffect(() => {
    fetchDistrictGeoJSON().then(setDistrictGeoJSON).catch(() => {});
  }, []);

  // Fetch layer data whenever activeLayer changes
  useEffect(() => {
    if (!activeLayer) { setLayerData(null); return; }
    let cancelled = false;
    (async () => {
      try {
        if (activeLayer.type === 'raster') {
          const data = await fetchRasterLayer(activeLayer.name);
          if (!cancelled) setLayerData({ layerType: 'raster', ...data });
        } else {
          const data = await fetchVectorLayer(activeLayer.name);
          if (!cancelled) setLayerData({ layerType: 'vector', geojson: data });
        }
      } catch {
        if (!cancelled) setLayerData(null);
      }
    })();
    return () => { cancelled = true; };
  }, [activeLayer]);

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
        selectedDistricts={selectedDistricts}
        onDistrictsChange={setSelectedDistricts}
        activeLayer={activeLayer}
        onLayerChange={setActiveLayer}
      />
      <main className="flex-1 relative">
        <MapView
          geojson={geojson}
          flyToRef={flyToRef}
          districtGeoJSON={districtGeoJSON}
          selectedDistricts={selectedDistricts}
          layerData={layerData}
          basemap={basemap}
          onBasemapChange={setBasemap}
        />
      </main>
    </div>
  );
}

