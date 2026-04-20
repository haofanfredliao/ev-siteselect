import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, GeoJSON, ImageOverlay } from 'react-leaflet';
import L from 'leaflet';
import { RANK_COLOURS, BASEMAPS } from '../utils/constants';
import { streetViewUrl } from '../utils/api';

// Fix default Leaflet icon path issue in bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function makeIcon(rank) {
  const colour = RANK_COLOURS[(rank - 1) % RANK_COLOURS.length];
  return L.divIcon({
    html: `<div style="
      background:${colour};color:#fff;border-radius:50%;
      width:30px;height:30px;display:flex;align-items:center;justify-content:center;
      font-weight:700;font-size:13px;border:2.5px solid #fff;
      box-shadow:0 2px 6px rgba(0,0,0,.35);">${rank}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    className: '',
  });
}

function FitBounds({ features }) {
  const map = useMap();
  useEffect(() => {
    if (!features || features.length === 0) return;
    const bounds = features.map(f => [
      f.geometry.coordinates[1],
      f.geometry.coordinates[0],
    ]);
    if (bounds.length > 0) map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
  }, [features, map]);
  return null;
}

function FlyToRef({ flyToRef }) {
  const map = useMap();
  useEffect(() => {
    flyToRef.current = (lat, lng) => map.setView([lat, lng], 15);
  }, [map, flyToRef]);
  return null;
}

function SitePopup({ rank, score, lat, lng }) {
  const colour = RANK_COLOURS[(rank - 1) % RANK_COLOURS.length];
  const svUrl = streetViewUrl(lat, lng);
  return (
    <div style={{ fontFamily: 'system-ui,sans-serif', minWidth: 200 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: colour, marginBottom: 4 }}>
        Candidate Site #{rank}
      </div>
      <div style={{ fontSize: 13, color: '#374151' }}>
        Suitability score: <strong style={{ color: '#059669' }}>{score.toFixed(3)}</strong>
      </div>
      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>
        {lat.toFixed(5)}°N, {lng.toFixed(5)}°E
      </div>
      <img
        src={svUrl}
        alt="Street View"
        style={{ width: '100%', borderRadius: 6, marginTop: 8 }}
        onError={e => { e.target.style.display = 'none'; }}
      />
    </div>
  );
}

// Basemap selector — rendered as a Leaflet-positioned control overlay
function BasemapControl({ basemap, onBasemapChange }) {
  return (
    <div
      className="leaflet-bottom leaflet-left"
      style={{ pointerEvents: 'auto', marginBottom: 24, marginLeft: 10 }}
    >
      <div className="leaflet-control bg-white rounded-lg shadow-md p-1.5 flex flex-col gap-0.5">
        <p className="text-xs text-gray-400 font-medium px-1 pb-0.5">Basemap</p>
        {BASEMAPS.map(bm => (
          <button
            key={bm.id}
            onClick={() => onBasemapChange(bm.id)}
            className={`text-xs px-2 py-1 rounded text-left transition-colors ${
              basemap === bm.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >{bm.label}</button>
        ))}
      </div>
    </div>
  );
}

// Dynamic basemap swap — swaps the TileLayer URL without remounting MapContainer
function DynamicTileLayer({ basemap }) {
  const bm = BASEMAPS.find(b => b.id === basemap) || BASEMAPS[0];
  return (
    <TileLayer
      key={bm.id}
      attribution={bm.attribution}
      url={bm.url}
      maxZoom={bm.maxZoom}
    />
  );
}

// Vector layer rendered as GeoJSON with simple point circles
function VectorOverlay({ geojson }) {
  if (!geojson) return null;
  return (
    <GeoJSON
      key={JSON.stringify(geojson.features?.length)}
      data={geojson}
      pointToLayer={(feature, latlng) => L.circleMarker(latlng, {
        radius: 4,
        fillColor: '#f97316',
        color: '#fff',
        weight: 1,
        fillOpacity: 0.75,
      })}
      style={() => ({ color: '#3b82f6', weight: 1.5, fillOpacity: 0.15 })}
    />
  );
}

// Map legend — shows gradient for rasters, dot for vector layers
function MapLegend({ layerData }) {
  if (!layerData) return null;

  return (
    <div
      className="leaflet-bottom leaflet-right"
      style={{ pointerEvents: 'none', marginBottom: 24, marginRight: 10 }}
    >
      <div className="leaflet-control bg-white rounded-lg shadow-md px-3 py-2 text-xs text-gray-600 min-w-[130px]">
        <p className="font-semibold text-gray-700 mb-1.5">{layerData.name || 'Layer'}</p>

        {layerData.layerType === 'raster' ? (
          /* Gradient bar for raster score layers */
          <>
            <div
              style={{
                height: 10,
                borderRadius: 4,
                background: 'linear-gradient(to right, #22c55e, #eab308, #ef4444)',
                marginBottom: 3,
              }}
            />
            <div className="flex justify-between text-gray-400">
              <span>Low</span>
              <span>High</span>
            </div>
          </>
        ) : (
          /* Dot indicator for vector raw data layers */
          <div className="flex items-center gap-1.5">
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: '#f97316',
                flexShrink: 0,
              }}
            />
            <span className="text-gray-500">Data point</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MapView({ geojson, flyToRef, districtGeoJSON, selectedDistricts, layerData, basemap, onBasemapChange }) {
  const features = geojson?.features || [];

  // Filter district GeoJSON to only the selected districts
  const filteredDistricts = districtGeoJSON && selectedDistricts?.length
    ? {
        ...districtGeoJSON,
        features: districtGeoJSON.features.filter(
          f => selectedDistricts.includes(f.properties?.name_en)
        ),
      }
    : districtGeoJSON;

  return (
    <MapContainer center={[22.3193, 114.1694]} zoom={11} style={{ height: '100%', width: '100%' }}>
      <DynamicTileLayer basemap={basemap} />

      {/* District boundary outlines — filtered to selected districts */}
      {filteredDistricts && (
        <GeoJSON
          key={`districts-${selectedDistricts?.join(',')}`}
          data={filteredDistricts}
          style={{ color: '#3b82f6', weight: 1.5, fill: false, opacity: 0.6 }}
        />
      )}

      {/* Data layer overlay (raster or vector) */}
      {layerData?.layerType === 'raster' && layerData.png_base64 && (
        <ImageOverlay
          url={`data:image/png;base64,${layerData.png_base64}`}
          bounds={layerData.bounds}
          opacity={0.75}
          zIndex={10}
        />
      )}
      {layerData?.layerType === 'vector' && (
        <VectorOverlay geojson={layerData.geojson} />
      )}

      <FitBounds features={features} />
      <FlyToRef flyToRef={flyToRef} />

      {/* Site markers (on top of all overlays) */}
      {features.map(f => {
        const [lng, lat] = f.geometry.coordinates;
        const { rank, score } = f.properties;
        return (
          <Marker key={rank} position={[lat, lng]} icon={makeIcon(rank)}>
            <Popup maxWidth={280}>
              <SitePopup rank={rank} score={score} lat={lat} lng={lng} />
            </Popup>
          </Marker>
        );
      })}

      <BasemapControl basemap={basemap} onBasemapChange={onBasemapChange} />
      <MapLegend layerData={layerData} />
    </MapContainer>
  );
}

