import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import GridGraph from '../../components/Grid/GridGraph';
import {
  getGridState, getMyListings, createListing, updateListing,
  getBidsForListing, respondToBid, getListings,
} from '../../services/api';

export default function SellerHome() {
  const { user } = useAuth();
  const { lastMessage } = useWebSocket();

  const [gridState, setGridState] = useState(null);
  const [myListing, setMyListing] = useState(null);
  const [allListings, setAllListings] = useState([]);
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Listing form
  const [amount, setAmount] = useState('');
  const [price, setPrice] = useState('');
  const [showPanel, setShowPanel] = useState(false);

  // Feasibility result display
  const [tradeResult, setTradeResult] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [grid, listings, myListingsData] = await Promise.all([
        getGridState().catch(() => null),
        getListings().catch(() => []),
        getMyListings().catch(() => []),
      ]);
      setGridState(grid);
      setAllListings(listings);

      const openListing = myListingsData.find(l => l.status === 'open' || l.status === 'partially_filled');
      setMyListing(openListing || null);

      if (openListing) {
        const listingBids = await getBidsForListing(openListing.listing_id).catch(() => []);
        setBids(listingBids);
        setAmount(openListing.amount_kwh_available.toString());
        setPrice(openListing.asking_price_per_kwh.toString());
      }
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Live updates via WebSocket
  useEffect(() => {
    if (lastMessage?.type === 'simulation_step' && lastMessage.data?.grid_state) {
      setGridState(lastMessage.data.grid_state);
    }
  }, [lastMessage]);

  const handleCreateListing = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    setActionLoading('create');
    try {
      const listing = await createListing(parseFloat(amount), parseFloat(price));
      setMyListing(listing);
      setSuccess('Listing created! Buyers can now see your offer on the grid map.');
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdateListing = async (e) => {
    e.preventDefault();
    if (!myListing) return;
    setError(''); setSuccess('');
    setActionLoading('update');
    try {
      const updated = await updateListing(myListing.listing_id, {
        amount_kwh_available: parseFloat(amount),
        asking_price_per_kwh: parseFloat(price),
      });
      setMyListing(updated);
      setSuccess('Listing updated.');
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCloseListing = async () => {
    if (!myListing) return;
    setActionLoading('close');
    try {
      await updateListing(myListing.listing_id, { status: 'closed' });
      setMyListing(null);
      setSuccess('Listing closed.');
      setBids([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRespondBid = async (bidId, action) => {
    setError(''); setSuccess(''); setTradeResult(null);
    setActionLoading(bidId);
    try {
      const result = await respondToBid(bidId, action);
      setTradeResult(result);

      if (result.status === 'executed') {
        setSuccess(result.message);
      } else if (result.status === 'partial_fill') {
        setSuccess(result.message);
      } else if (result.status === 'rejected') {
        setError(result.message);
      }

      // Refresh data
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <div className="loading-overlay"><div className="spinner"></div><span>Loading...</span></div>;
  }

  return (
    <div className="dashboard-grid">
      {/* Success / Error banners */}
      {success && <div className="alert alert-success">{success}<button className="alert-close" onClick={() => setSuccess('')}>×</button></div>}
      {error && <div className="alert alert-error">{error}<button className="alert-close" onClick={() => setError('')}>×</button></div>}

      {/* Grid Map */}
      <div className="main-grid">
        <div className="flex flex-col gap-lg">
          <GridGraph
            gridState={gridState}
            highlightBus={user?.bus_id}
            listings={allListings}
            role="seller"
            onBusClick={(busId) => {
              if (busId === user?.bus_id) setShowPanel(true);
            }}
          />
        </div>

        {/* Side Panel */}
        <div className="flex flex-col gap-lg">
          {/* Listing Management */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">📋 Your Listing</span>
              {myListing && <span className={`badge ${myListing.status === 'open' ? 'executed' : 'partial'}`}>{myListing.status}</span>}
            </div>

            <form onSubmit={myListing ? handleUpdateListing : handleCreateListing}>
              <div className="form-group">
                <label className="form-label">Energy Available (kWh)</label>
                <input
                  type="number"
                  className="form-input"
                  value={amount}
                  onChange={e => setAmount(e.target.value)}
                  step="0.1"
                  min="0.1"
                  max="1000"
                  required
                  placeholder="e.g. 5.0"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Price (₹/kWh)</label>
                <input
                  type="number"
                  className="form-input"
                  value={price}
                  onChange={e => setPrice(e.target.value)}
                  step="0.01"
                  min="0.01"
                  max="100"
                  required
                  placeholder="e.g. 4.50"
                />
              </div>

              <div className="flex gap-sm">
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                  disabled={actionLoading === 'create' || actionLoading === 'update'}
                >
                  {actionLoading === 'create' || actionLoading === 'update' ? (
                    <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Saving...</>
                  ) : myListing ? 'Update Listing' : 'Create Listing'}
                </button>
                {myListing && (
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={handleCloseListing}
                    disabled={actionLoading === 'close'}
                  >
                    Close
                  </button>
                )}
              </div>
            </form>
          </div>

          {/* Incoming Bids */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">📨 Incoming Bids</span>
              <span className="text-xs text-muted">{bids.filter(b => b.status === 'pending').length} pending</span>
            </div>

            {bids.length === 0 ? (
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>
                {myListing ? 'No bids yet. Buyers will bid when they see your listing.' : 'Create a listing to receive bids.'}
              </p>
            ) : (
              <div className="bid-list">
                {bids.map(bid => (
                  <div key={bid.bid_id} className="bid-item">
                    <div className="bid-info">
                      <span className="bid-buyer">{bid.buyer_name || `Buyer (Bus ${bid.bus_id})`}</span>
                      <span className="text-mono text-sm">
                        {bid.requested_amount_kwh.toFixed(2)} kWh @ ₹{bid.offered_price_per_kwh.toFixed(2)}/kWh
                      </span>
                      <span className={`badge ${bid.status === 'pending' ? 'pending' : bid.status === 'accepted' ? 'executed' : 'rejected'}`}>
                        {bid.status}
                      </span>
                    </div>
                    {bid.status === 'pending' && (
                      <div className="bid-actions">
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleRespondBid(bid.bid_id, 'accept')}
                          disabled={actionLoading === bid.bid_id}
                        >
                          {actionLoading === bid.bid_id ? (
                            <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }}></div>
                          ) : 'Accept'}
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleRespondBid(bid.bid_id, 'reject')}
                          disabled={actionLoading === bid.bid_id}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Feasibility Result */}
          {tradeResult && (
            <div className={`card feasibility-result ${tradeResult.status}`}>
              <div className="card-header">
                <span className="card-title">⚡ Trade Result</span>
                <span className={`badge ${tradeResult.status === 'executed' ? 'executed' : tradeResult.status === 'partial_fill' ? 'partial' : 'rejected'}`}>
                  {tradeResult.status.replace('_', ' ')}
                </span>
              </div>
              <p className="text-sm" style={{ marginBottom: 8 }}>{tradeResult.message}</p>
              {tradeResult.amount_kwh != null && (
                <p className="text-mono text-sm text-muted">
                  {tradeResult.amount_kwh.toFixed(3)} kWh @ ₹{tradeResult.price_per_kwh?.toFixed(2)}/kWh
                  = ₹{tradeResult.total_price?.toFixed(2)}
                </p>
              )}
              <button className="btn btn-ghost btn-sm mt-sm" onClick={() => setTradeResult(null)}>Dismiss</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
