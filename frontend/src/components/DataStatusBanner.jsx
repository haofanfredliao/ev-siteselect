export default function DataStatusBanner({ allReady, error }) {
  if (error) {
    return (
      <div className="rounded-xl border px-3 py-2 mb-2 text-sm bg-red-50 border-red-300">
        <p className="font-medium text-xs text-red-700">{error}</p>
      </div>
    );
  }
  if (allReady) {
    return (
      <div className="rounded-xl border px-3 py-2 mb-2 text-sm bg-emerald-50 border-emerald-300">
        <p className="font-medium text-xs text-emerald-700">All data ready — run analysis below.</p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border px-3 py-2 mb-2 text-sm bg-amber-50 border-amber-300">
      <p className="font-medium text-xs text-amber-700">Some factors need preprocessing.</p>
    </div>
  );
}
