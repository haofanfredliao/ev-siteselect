import { RANK_COLOURS } from '../utils/constants';

export default function ResultsList({ geojson, onFlyTo }) {
  const features = geojson?.features || [];
  if (features.length === 0) return null;

  return (
    <div>
      <hr className="border-gray-100 mb-3" />
      <div className="flex justify-between items-center mb-2">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">Top Sites</h2>
        <span className="text-xs text-gray-400">{features.length} site{features.length !== 1 ? 's' : ''}</span>
      </div>
      <div className="space-y-1.5">
        {features.map(f => {
          const [lng, lat] = f.geometry.coordinates;
          const { rank, score } = f.properties;
          const colour = RANK_COLOURS[(rank - 1) % RANK_COLOURS.length];
          return (
            <button
              key={rank}
              onClick={() => onFlyTo(lat, lng)}
              className="w-full text-left border border-gray-200 rounded-lg px-3 py-2
                         hover:bg-blue-50 transition-colors text-sm"
            >
              <div className="flex items-center justify-between">
                <span
                  className="inline-flex items-center justify-center w-6 h-6 rounded-full text-white text-xs font-bold"
                  style={{ background: colour }}
                >{rank}</span>
                <span className="font-semibold text-emerald-600">{score.toFixed(3)}</span>
              </div>
              <div className="text-gray-400 text-xs mt-0.5">
                {lat.toFixed(4)}°N, {lng.toFixed(4)}°E
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
