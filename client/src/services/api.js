const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function getAuthHeaders() {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: getAuthHeaders(),
    ...options,
    headers: { ...getAuthHeaders(), ...options.headers },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function authFetch(url, options = {}) {
  return fetchJSON(url, options);
}

// Grid endpoints
export const getGridTopology = () => fetchJSON('/grid/topology');
export const getGridState = () => fetchJSON('/grid/state');
export const getHouseholds = () => fetchJSON('/grid/households');

// Trade endpoints
export const getTrades = (limit = 50, skip = 0) => fetchJSON(`/trades?limit=${limit}&skip=${skip}`);
export const getTradeStats = () => fetchJSON('/trades/stats');
export const verifyChain = () => fetchJSON('/trades/verify-chain');
export const getMyTrades = (limit = 50) => authFetch(`/trades/mine?limit=${limit}`);
export const getAllTrades = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.limit) qs.set('limit', params.limit);
  if (params.skip) qs.set('skip', params.skip);
  if (params.status) qs.set('status_filter', params.status);
  if (params.buyerId) qs.set('buyer_id', params.buyerId);
  if (params.sellerId) qs.set('seller_id', params.sellerId);
  return authFetch(`/trades/all?${qs.toString()}`);
};

// Listing endpoints
export const getListings = (statusFilter = 'open') =>
  fetchJSON(`/listings?status_filter=${statusFilter}`);
export const getMyListings = () => authFetch('/listings/mine');
export const createListing = (amountKwh, pricePerKwh) =>
  authFetch('/listings', {
    method: 'POST',
    body: JSON.stringify({
      amount_kwh_available: amountKwh,
      asking_price_per_kwh: pricePerKwh,
    }),
  });
export const updateListing = (listingId, updates) =>
  authFetch(`/listings/${listingId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });

// Bid endpoints
export const placeBid = (listingId, amountKwh, pricePerKwh) =>
  authFetch('/bids', {
    method: 'POST',
    body: JSON.stringify({
      listing_id: listingId,
      requested_amount_kwh: amountKwh,
      offered_price_per_kwh: pricePerKwh,
    }),
  });
export const respondToBid = (bidId, action) =>
  authFetch(`/bids/${bidId}/respond`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  });
export const getMyBids = () => authFetch('/bids/mine');
export const getBidsForListing = (listingId) =>
  authFetch(`/bids/for-listing/${listingId}`);

// Admin endpoints
export const getAdminStats = () => authFetch('/admin/stats');

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
