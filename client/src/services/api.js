const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function fetchJSON(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// Grid endpoints
export const getGridTopology = () => fetchJSON('/grid/topology');
export const getGridState = () => fetchJSON('/grid/state');
export const getHouseholds = () => fetchJSON('/grid/households');

// Trade endpoints
export const getTrades = (limit = 50, skip = 0) => fetchJSON(`/trades?limit=${limit}&skip=${skip}`);
export const getTradeStats = () => fetchJSON('/trades/stats');
export const verifyChain = () => fetchJSON('/trades/verify-chain');

// Simulation endpoints
export const startSimulation = (totalTimesteps = 96, speedMultiplier = 1.0) =>
  fetchJSON('/simulation/start', {
    method: 'POST',
    body: JSON.stringify({ total_timesteps: totalTimesteps, speed_multiplier: speedMultiplier }),
  });

export const stopSimulation = () =>
  fetchJSON('/simulation/stop', { method: 'POST' });

export const stepSimulation = (timestepIdx = null) =>
  fetchJSON('/simulation/step', {
    method: 'POST',
    body: JSON.stringify({ timestep_idx: timestepIdx }),
  });

export const getSimulationStatus = () => fetchJSON('/simulation/status');

export const resetSimulation = () =>
  fetchJSON('/simulation/reset', { method: 'POST' });

// Health
export const getHealth = () => fetchJSON('/health');
