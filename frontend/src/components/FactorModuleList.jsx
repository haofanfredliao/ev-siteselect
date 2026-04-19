import { useState } from 'react';
import { FACTOR_DEFS } from '../utils/constants';
import FactorModule from './FactorModule';

export default function FactorModuleList({ factors, sources, onUpdate, onRemove, onAdd }) {
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const totalWeight = factors.reduce((s, f) => s + f.weight, 0);

  const activeKeys = new Set(factors.map(f => f.key));
  const availableToAdd = Object.keys(FACTOR_DEFS).filter(k => !activeKeys.has(k));

  return (
    <div>
      <div className="space-y-2.5">
        {factors.map(f => (
          <FactorModule
            key={f.key}
            factor={f}
            sources={sources[f.key] || []}
            totalWeight={totalWeight}
            onUpdate={onUpdate}
            onRemove={onRemove}
          />
        ))}
      </div>

      {/* Add factor button */}
      {availableToAdd.length > 0 && (
        <div className="mt-2 relative">
          <button
            onClick={() => setAddMenuOpen(v => !v)}
            className="w-full py-1.5 text-xs font-medium text-blue-600 border border-dashed border-blue-300 rounded-lg
                       hover:bg-blue-50 transition-colors"
          >
            + Add Factor
          </button>
          {addMenuOpen && (
            <div className="absolute left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
              {availableToAdd.map(k => (
                <button
                  key={k}
                  onClick={() => { onAdd(k); setAddMenuOpen(false); }}
                  className="block w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-blue-50 transition-colors"
                >
                  {FACTOR_DEFS[k].emoji} {FACTOR_DEFS[k].label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
