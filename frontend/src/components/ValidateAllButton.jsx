import { useState } from 'react';
import { fetchStatus, triggerPreprocessAll } from '../utils/api';

export default function ValidateAllButton({ onStatusUpdate }) {
  const [running, setRunning] = useState(false);
  const [validating, setValidating] = useState(false);

  const handleValidate = async () => {
    setValidating(true);
    try {
      const status = await fetchStatus();
      onStatusUpdate(status);
    } catch { /* ignore */ } finally {
      setValidating(false);
    }
  };

  const handlePreprocessAll = async () => {
    setRunning(true);
    try {
      await triggerPreprocessAll();
    } catch { /* ignore */ } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex gap-2 mt-3">
      <button
        onClick={handleValidate}
        disabled={validating}
        className="flex-1 py-2 text-xs font-medium rounded-lg transition-colors
                   bg-sky-500 hover:bg-sky-600 text-white disabled:opacity-50"
      >
        {validating ? '⏳ Checking...' : '✔ Validate All'}
      </button>
      <button
        onClick={handlePreprocessAll}
        disabled={running}
        className="flex-1 py-2 text-xs font-medium rounded-lg transition-colors
                   bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-50"
      >
        {running ? '⏳ Running...' : '▶ Preprocess All'}
      </button>
    </div>
  );
}
