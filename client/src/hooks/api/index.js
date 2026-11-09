import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../../services/api';

// --- Grid Hooks ---
export const useGridTopology = () => useQuery({
  queryKey: ['grid', 'topology'],
  queryFn: api.getGridTopology
});

export const useGridState = () => useQuery({
  queryKey: ['grid', 'state'],
  queryFn: api.getGridState
});

export const useHouseholds = () => useQuery({
  queryKey: ['grid', 'households'],
  queryFn: api.getHouseholds
});

// --- Listing Hooks ---
export const useListings = (statusFilter = 'open') => useQuery({
  queryKey: ['listings', statusFilter],
  queryFn: () => api.getListings(statusFilter)
});

export const useMyListings = () => useQuery({
  queryKey: ['listings', 'mine'],
  queryFn: api.getMyListings
});

export const useCreateListing = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ powerKw, durationHours, pricePerKwh }) => api.createListing(powerKw, durationHours, pricePerKwh),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['listings', 'mine'] });
    }
  });
};

export const useUpdateListing = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listingId, updates }) => api.updateListing(listingId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['listings', 'mine'] });
    }
  });
};

// --- Bid Hooks ---
export const useMyBids = () => useQuery({
  queryKey: ['bids', 'mine'],
  queryFn: api.getMyBids
});

export const useBidsForListing = (listingId) => useQuery({
  queryKey: ['bids', 'listing', listingId],
  queryFn: () => (listingId ? api.getBidsForListing(listingId) : Promise.resolve([])),
  enabled: !!listingId,
});

export const usePlaceBid = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listingId, powerKw, durationHours, pricePerKwh }) => api.placeBid(listingId, powerKw, durationHours, pricePerKwh),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bids'] });
      queryClient.invalidateQueries({ queryKey: ['bids', 'mine'] });
    }
  });
};

export const usePreviewBid = () => useMutation({
  mutationFn: ({ listingId, powerKw, durationHours }) => api.previewBid(listingId, powerKw, durationHours),
});

export const useRespondToBid = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ bidId, action }) => api.respondToBid(bidId, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bids'] });
      queryClient.invalidateQueries({ queryKey: ['bids', 'mine'] });
      queryClient.invalidateQueries({ queryKey: ['listings'] });
    }
  });
};

// --- Trade Hooks ---
export const useTrades = (limit = 50, skip = 0) => useQuery({
  queryKey: ['trades', { limit, skip }],
  queryFn: () => api.getTrades(limit, skip)
});

export const useAllTrades = (params = {}) => useQuery({
  queryKey: ['trades', 'all', params],
  queryFn: () => api.getAllTrades(params)
});

export const useTradeStats = () => useQuery({
  queryKey: ['trades', 'stats'],
  queryFn: api.getTradeStats
});

export const useVerifyChain = () => useQuery({
  queryKey: ['trades', 'verify'],
  queryFn: api.verifyChain
});

export const useMyTrades = (limit = 50) => useQuery({
  queryKey: ['trades', 'mine', limit],
  queryFn: () => api.getMyTrades(limit)
});

// --- Admin Hooks ---
export const useAdminStats = () => useQuery({
  queryKey: ['admin', 'stats'],
  queryFn: api.getAdminStats
});

// --- Simulation Hooks ---
export const useStartSimulation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ totalTimesteps, speedMultiplier }) => api.startSimulation(totalTimesteps, speedMultiplier),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grid', 'state'] });
    }
  });
};

export const useStopSimulation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.stopSimulation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grid', 'state'] });
    }
  });
};

export const useStepSimulation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (timestepIdx) => api.stepSimulation(timestepIdx),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grid', 'state'] });
    }
  });
};

export const useResetSimulation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.resetSimulation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grid', 'state'] });
    }
  });
};
