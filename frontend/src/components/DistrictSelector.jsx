import { ALL_DISTRICTS } from '../utils/constants';

export default function DistrictSelector({ selected, onChange }) {
  const allSelected = selected.length === ALL_DISTRICTS.length;

  const toggle = (name) => {
    if (selected.includes(name)) {
      onChange(selected.filter(n => n !== name));
    } else {
      onChange([...selected, name]);
    }
  };

  return (
    <div>
      {/* Quick-select buttons */}
      <div className="flex gap-1.5 mb-2">
        <button
          onClick={() => onChange(ALL_DISTRICTS)}
          disabled={allSelected}
          className="text-xs px-2 py-0.5 rounded border border-blue-300 text-blue-600
                     hover:bg-blue-50 disabled:opacity-40 transition-colors"
        >All</button>
        <button
          onClick={() => onChange([])}
          disabled={selected.length === 0}
          className="text-xs px-2 py-0.5 rounded border border-gray-300 text-gray-500
                     hover:bg-gray-50 disabled:opacity-40 transition-colors"
        >None</button>
        <span className="ml-auto text-xs text-gray-400 self-center">
          {selected.length}/{ALL_DISTRICTS.length}
        </span>
      </div>

      {/* District checkboxes — 2 columns */}
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 max-h-44 overflow-y-auto pr-0.5">
        {ALL_DISTRICTS.map(name => {
          const short = name.replace(' District', '');
          return (
            <label
              key={name}
              className="flex items-center gap-1 text-xs cursor-pointer py-0.5
                         hover:text-gray-800 text-gray-600"
            >
              <input
                type="checkbox"
                checked={selected.includes(name)}
                onChange={() => toggle(name)}
                className="accent-blue-600 w-3 h-3 flex-shrink-0"
              />
              <span className="truncate">{short}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
