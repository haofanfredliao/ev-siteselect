import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { RANK_COLOURS } from '../utils/constants';
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

export default function MapView({ geojson, flyToRef }) {
  const features = geojson?.features || [];

  return (
    <MapContainer center={[22.3193, 114.1694]} zoom={11} style={{ height: '100%', width: '100%' }}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />
      <FitBounds features={features} />
      <FlyToRef flyToRef={flyToRef} />
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
    </MapContainer>
  );
}
