import { useState, useCallback } from 'react';
import { FACTOR_DEFS } from '../utils/constants';

const DEFAULT_FACTORS = Object.keys(FACTOR_DEFS).map(key => ({
  key,
  weight: 50,
  source: '',          // empty = use default
  status: 'unknown',   // unknown | ready | pending | error
}));

export default function useFactors() {
  const [factors, setFactors] = useState(DEFAULT_FACTORS);

  const updateFactor = useCallback((key, patch) => {
    setFactors(prev => prev.map(f => f.key === key ? { ...f, ...patch } : f));
  }, []);

  const addFactor = useCallback((key) => {
    setFactors(prev => {
      if (prev.some(f => f.key === key)) return prev;
      return [...prev, { key, weight: 50, source: '', status: 'unknown' }];
    });
  }, []);

  const removeFactor = useCallback((key) => {
    setFactors(prev => prev.filter(f => f.key !== key));
  }, []);

  const setWeightsBatch = useCallback((weightsObj) => {
    setFactors(prev => prev.map(f => ({
      ...f,
      weight: weightsObj[f.key] != null ? weightsObj[f.key] : f.weight,
    })));
  }, []);

  // Compute normalised weights from current factor list
  const collectWeights = useCallback(() => {
    const total = factors.reduce((s, f) => s + f.weight, 0) || 1;
    const out = {};
    for (const f of factors) out[f.key] = f.weight / total;
    return out;
  }, [factors]);

  // Sync status from API status response
  // statusData includes: { [label]: bool, running_factors: string[] }
  const syncStatus = useCallback((statusData) => {
    const running = Array.isArray(statusData.running_factors) ? statusData.running_factors : [];
    setFactors(prev => prev.map(f => {
      const label = {
        population: 'Population Density',
        poi: 'POI Density',
        road_accessibility: 'Road Accessibility',
        ev_competition: 'EV Competition',
        slope: 'Slope Suitability',
        landuse: 'Land Use Score',
      }[f.key];
      const ready = label ? statusData[label] : false;
      if (running.includes(f.key)) return { ...f, status: 'running' };
      return { ...f, status: ready ? 'ready' : 'unknown' };
    }));
  }, []);

  return { factors, updateFactor, addFactor, removeFactor, setWeightsBatch, collectWeights, syncStatus };
}
