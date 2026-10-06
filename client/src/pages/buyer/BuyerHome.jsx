import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import GridGraph from '../../components/Grid/GridGraph';
import { getGridState, getListings, placeBid, getMyBids } from '../../services/api';

export default function BuyerHome() {
  const { user } = useAuth();
  const { lastMessage } = useWebSocket();

  const [gridState, setGridState] = useState(null);
  const [listings, setListings] = useState([]);
  const [myBids, setMyBids] = useState([]);
  const [selectedListing, setSelectedListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidLoading, setBidLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Bid form
  const [bidAmount, setBidAmount] = useState('');
  const [bidPrice, setBidPrice] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const [grid, listingsData, bidsData] = await Promise.all([
        getGridState().catch(() => null),
        getListings().catch(() => []),
        getMyBids().catch(() => []),
      ]);
      setGridState(grid);
      setListings(listingsData);
      setMyBids(bidsData);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Live updates
  useEffect(() => {
    if (lastMessage?.type === 'simulation_step' && lastMessage.data?.grid_state) {
      setGridState(lastMessage.data.grid_state);
    }
  }, [lastMessage]);

  const handleSelectListing = (listing) => {
    setSelectedListing(listing);
    setBidAmount(listing.amount_kwh_available.toString());
    setBidPrice(listing.asking_price_per_kwh.toString());
    setError('');
    setSuccess('');
  };

  const handlePlaceBid = async (e) => {
    e.preventDefault();
    if (!selectedListing) return;
    setError(''); setSuccess('');
    setBidLoading(true);
    try {
      await placeBid(selectedListing.listing_id, parseFloat(bidAmount), parseFloat(bidPrice));
      setSuccess('Bid placed! You will be notified when the seller responds.');
      setSelectedListing(null);
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setBidLoading(false);
    }
  };

  if (loading) {
    return <div className="loading-overlay"><div className="spinner"></div><span>Loading...</span></div>;
  }

  return (
    <div className="dashboard-grid">
      {success && <div className="alert alert-success">{success}<button className="alert-close" onClick={() => setSuccess('')}>×</button></div>}
      {error && <div className="alert alert-error">{error}<button className="alert-close" onClick={() => setError('')}>×</button></div>}

      <div className="main-grid">
        <div className="flex flex-col gap-lg">
          <GridGraph
            gridState={gridState}
            highlightBus={user?.bus_id}
            listings={listings}
            role="buyer"
            onBusClick={(busId) => {
              const listing = listings.find(l => l.bus_id === busId);
              if (listing) handleSelectListing(listing);
            }}
          />

          {/* Open Listings Table */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">🏷️ Available Listings</span>
              <span className="text-xs text-muted">{listings.length} open</span>
            </div>
            {listings.length === 0 ? (
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>No sellers have listed energy yet.</p>
            ) : (
              <div className="listings-grid">
                {listings.map(listing => (
                  <div
                    key={listing.listing_id}
                    className={`listing-card ${selectedListing?.listing_id === listing.listing_id ? 'selected' : ''}`}
                    onClick={() => handleSelectListing(listing)}
                  >
                    <div className="listing-card-header">
                      <span className="listing-bus">Bus {listing.bus_id}</span>
                      <span className="listing-seller">{listing.seller_name}</span>
                    </div>
                    <div className="listing-card-body">
                      <div className="listing-stat">
                        <span className="listing-stat-value text-mono">{listing.amount_kwh_available.toFixed(1)}</span>
                        <span className="listing-stat-label">kWh</span>
                      </div>
                      <div className="listing-stat">
                        <span className="listing-stat-value text-mono text-green">₹{listing.asking_price_per_kwh.toFixed(2)}</span>
                        <span className="listing-stat-label">per kWh</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Panel */}
        <div className="flex flex-col gap-lg">
          {/* Bid Form */}
          {selectedListing ? (
            <div className="card card-highlight">
              <div className="card-header">
                <span className="card-title">💰 Place Bid</span>
                <button className="btn btn-ghost btn-sm" onClick={() => setSelectedListing(null)}>×</button>
              </div>
              <p className="text-sm text-muted mb-md">
                Bidding on <strong>{selectedListing.seller_name}'s</strong> listing (Bus {selectedListing.bus_id})
              </p>

              <form onSubmit={handlePlaceBid}>
                <div className="form-group">
                  <label className="form-label">Amount (kWh)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={bidAmount}
                    onChange={e => setBidAmount(e.target.value)}
                    step="0.1"
                    min="0.1"
                    max={selectedListing.amount_kwh_available}
                    required
                  />
                  <span className="text-xs text-muted">Max: {selectedListing.amount_kwh_available.toFixed(1)} kWh</span>
                </div>
                <div className="form-group">
                  <label className="form-label">Your Price Offer (₹/kWh)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={bidPrice}
                    onChange={e => setBidPrice(e.target.value)}
                    step="0.01"
                    min="0.01"
                    required
                  />
                  <span className="text-xs text-muted">Asking: ₹{selectedListing.asking_price_per_kwh.toFixed(2)}/kWh</span>
                </div>
                <button
                  type="submit"
                  className="btn btn-primary auth-submit"
                  disabled={bidLoading}
                >
                  {bidLoading ? (
                    <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Placing bid...</>
                  ) : 'Place Bid'}
                </button>
              </form>
            </div>
          ) : (
            <div className="card">
              <div className="card-header">
                <span className="card-title">💰 Place Bid</span>
              </div>
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>
                Click on a seller's house on the map or a listing card to place a bid.
              </p>
            </div>
          )}

          {/* My Bids */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">📋 My Bids</span>
              <span className="text-xs text-muted">{myBids.length} total</span>
            </div>
            {myBids.length === 0 ? (
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>No bids placed yet.</p>
            ) : (
              <div className="bid-list">
                {myBids.map(bid => (
                  <div key={bid.bid_id} className="bid-item">
                    <div className="bid-info">
                      <span className="text-sm">Listing: Bus {bid.bus_id || '?'}</span>
                      <span className="text-mono text-xs">
                        Requested: {bid.requested_amount_kwh?.toFixed(2)} kWh @ ₹{bid.offered_price_per_kwh?.toFixed(2)}
                      </span>
                      {bid.scheduled_amount_kwh != null && (
                        <span className="text-mono text-xs text-muted">
                          Scheduled: {bid.scheduled_amount_kwh?.toFixed(2)} kWh
                          {bid.final_amount_kwh != null && ` → Delivered: ${bid.final_amount_kwh?.toFixed(2)} kWh`}
                        </span>
                      )}
                    </div>
                    <span className={`badge ${bid.status === 'pending' ? 'pending' : bid.status === 'accepted' ? 'executed' : bid.status === 'feasibility_partial' ? 'partial' : 'rejected'}`}>
                      {bid.status?.replace(/_/g, ' ')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
