import { useState, useEffect } from 'react';
import { fetchResults, fetchResultFile } from '../utils/api';

export default function ResultHistory({ onLoadResult }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try {
      const data = await fetchResults();
      setFiles(data.results || []);
    } catch { /* ignore */ }
  };

  useEffect(() => { refresh(); }, []);

  const handleLoad = async (filename) => {
    setLoading(true);
    try {
      const geojson = await fetchResultFile(filename);
      onLoadResult(geojson);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  if (files.length === 0) return null;

  return (
    <div className="mt-2">
      <label className="text-xs font-semibold text-gray-400 uppercase tracking-widest block mb-1">
        Result History
      </label>
      <div className="flex gap-1">
        <select
          onChange={e => { if (e.target.value) handleLoad(e.target.value); }}
          disabled={loading}
          className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 bg-gray-50
                     focus:outline-none focus:ring-1 focus:ring-blue-400"
          defaultValue=""
        >
          <option value="" disabled>Load a previous result…</option>
          {files.map(f => (
            <option key={f} value={f}>{f.replace('result_', '').replace('.geojson', '')}</option>
          ))}
        </select>
        <button onClick={refresh} className="text-xs text-blue-600 hover:underline">↻</button>
      </div>
    </div>
  );
}
