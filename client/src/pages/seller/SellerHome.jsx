import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import GridGraph from '../../components/Grid/GridGraph';
import {
  useGridState,
  useMyListings,
  useListings,
  useCreateListing,
  useUpdateListing,
  useBidsForListing,
  useRespondToBid
} from '../../hooks/api';
import { Card, Button, Input, Badge, PageIntro, StatCard } from '../../components/ui';

export default function SellerHome() {
  const { user } = useAuth();

  // Data from React Query
  const { data: gridState, isLoading: gridLoading } = useGridState();
  const { data: allListings = [], isLoading: allListingsLoading } = useListings();
  const { data: myListings = [], isLoading: myListingsLoading } = useMyListings();

  // The active open listing for this seller
  const myListing = myListings.find(l => l.status === 'open' || l.status === 'partially_filled');

  const { data: bids = [], isLoading: bidsLoading } = useBidsForListing(myListing?.listing_id);

  // Mutations
  const { mutateAsync: createListing, isPending: isCreating } = useCreateListing();
  const { mutateAsync: updateListing, isPending: isUpdating } = useUpdateListing();
  const { mutate: respondToBid, isPending: isResponding } = useRespondToBid();

  // Local form state
  const [amount, setAmount] = useState('');
  const [duration, setDuration] = useState('1');
  const [price, setPrice] = useState('');
  const [localError, setLocalError] = useState('');
  const [localSuccess, setLocalSuccess] = useState('');
  const [tradeResult, setTradeResult] = useState(null);

  // Init form values when listing is loaded
  useEffect(() => {
    if (myListing) {
      setAmount((myListing.power_kw || myListing.amount_kwh_available).toString());
      setPrice(myListing.asking_price_per_kwh.toString());
      setDuration((myListing.duration_hours || 1).toString());
    }
  }, [myListing]);

  const handleListingSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    setLocalSuccess('');

    try {
      if (myListing) {
        const result = await updateListing({
          listingId: myListing.listing_id,
          updates: {
            power_kw: parseFloat(amount),
            duration_hours: parseFloat(duration),
            asking_price_per_kwh: parseFloat(price)
          }
        });
        setLocalSuccess(result.feasibility_preview?.feasible
          ? `Listing updated. Grid preview: ${result.feasibility_preview.feasible.power_kw.toFixed(2)} kW for ${result.feasibility_preview.feasible.duration_hours.toFixed(2)} h.`
          : 'Listing updated. A buyer route will be checked when a bid arrives.');
      } else {
        const result = await createListing({
          powerKw: parseFloat(amount),
          durationHours: parseFloat(duration),
          pricePerKwh: parseFloat(price)
        });
        setLocalSuccess(result.feasibility_preview?.feasible
          ? `Listing created. Safe preview: ${result.feasibility_preview.feasible.power_kw.toFixed(2)} kW for ${result.feasibility_preview.feasible.duration_hours.toFixed(2)} h.`
          : 'Listing created! Buyer-specific feasibility will be checked before acceptance.');
      }
    } catch (err) {
      setLocalError(err.message);
    }
  };

  const handleCloseListing = async () => {
    if (!myListing) return;
    try {
      await updateListing({
        listingId: myListing.listing_id,
        updates: { status: 'closed' }
      });
      setLocalSuccess('Listing closed.');
    } catch (err) {
      setLocalError(err.message);
    }
  };

  const handleRespondBid = async (bidId, action) => {
    setLocalError('');
    setLocalSuccess('');
    setTradeResult(null);

    try {
      const result = await respondToBid({ bidId, action });
      setTradeResult(result);

      if (result.status === 'executed' || result.status === 'partial_fill') {
        setLocalSuccess(result.message);
      } else if (result.status === 'rejected') {
        setLocalError(result.message);
      }
    } catch (err) {
      setLocalError(err.message);
    }
  };

  if (gridLoading || allListingsLoading || myListingsLoading || bidsLoading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <span className="text-muted">Loading Seller Portal...</span>
      </div>
    );
  }

  return (
    <div className="dashboard-grid">
      <PageIntro
        eyebrow={`Seller workspace / Bus ${user?.bus_id ?? '—'}`}
        title="Your energy, working harder."
        description="Publish your surplus, respond to demand, and let the grid-aware market handle the rest."
      />
      <div className="stats-row">
        <StatCard label="Open listing" value={myListing ? `${(myListing.power_kw || myListing.amount_kwh_available)?.toFixed(1)} kW` : 'None'} detail={myListing ? `${Math.round(myListing.units_available || myListing.amount_kwh_available * 100)} units · visible to buyers` : 'Create one below'} />
        <StatCard label="Incoming bids" value={bids.length} detail="Offers awaiting your review" accent="amber" />
        <StatCard label="Network status" value="Stable" detail="AI safety gate active" accent="blue" />
      </div>
      {localSuccess && (
        <div className="alert alert-success">
          {localSuccess}
          <button className="alert-close" onClick={() => setLocalSuccess('')}>×</button>
        </div>
      )}
      {localError && (
        <div className="alert alert-error">
          {localError}
          <button className="alert-close" onClick={() => setLocalError('')}>×</button>
        </div>
      )}

      <div className="main-grid">
        <div className="flex flex-col gap-lg">
          <Card title="Grid Connectivity & Energy Flow">
            <GridGraph
              gridState={gridState}
              highlightBus={user?.bus_id}
              listings={allListings}
              role="seller"
              onBusClick={(busId) => {
                if (busId === user?.bus_id) {
                  // Handled by the right panel being present
                }
              }}
            />
          </Card>
        </div>

        <div className="flex flex-col gap-lg">
          {/* Listing Management */}
          <Card title={`Your Listing ${myListing ? `(${myListing.status})` : ''}`}>
            <form onSubmit={handleListingSubmit} className="flex flex-col gap-md">
              <Input
                label="Power Available (kW)"
                type="number"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                step="0.1"
                min="0.1"
                max="1000"
                required
                placeholder="e.g. 5.0"
              />
              <Input
                label="Delivery Duration (hours)"
                type="number"
                value={duration}
                onChange={e => setDuration(e.target.value)}
                step="0.25"
                min="0.25"
                max="24"
                required
                placeholder="e.g. 2"
              />
              <div className="text-xs text-muted">
                {((parseFloat(amount) || 0) * (parseFloat(duration) || 0)).toFixed(2)} kWh · {Math.round((parseFloat(amount) || 0) * (parseFloat(duration) || 0) * 100)} units (10 Wh each)
              </div>
              <Input
                label="Price (₹/kWh)"
                type="number"
                value={price}
                onChange={e => setPrice(e.target.value)}
                step="0.01"
                min="0.01"
                max="100"
                required
                placeholder="e.g. 4.50"
              />

              <div className="flex gap-sm">
                <Button
                  type="submit"
                  variant="primary"
                  className="flex-1"
                  disabled={isCreating || isUpdating}
                >
                  {(isCreating || isUpdating) ? (
                    <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Saving...</>
                  ) : myListing ? 'Update Listing' : 'Create Listing'}
                </Button>
                {myListing && (
                  <Button
                    type="button"
                    variant="danger"
                    onClick={handleCloseListing}
                    disabled={isUpdating}
                  >
                    Close
                  </Button>
                )}
              </div>
            </form>
          </Card>

          {/* Incoming Bids */}
          <Card title={`Incoming Bids (${bids.filter(b => b.status === 'pending').length})`}>
            {bids.length === 0 ? (
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>
                {myListing ? 'No bids yet. Buyers will bid when they see your listing.' : 'Create a listing to receive bids.'}
              </p>
            ) : (
              <div className="bid-list">
                {bids.map(bid => (
                  <div key={bid.bid_id} className="bid-item">
                    <div className="bid-info">
                      <span className="text-sm font-medium">{bid.buyer_name || `Buyer (Bus ${bid.bus_id})`}</span>
                      <span className="text-mono text-xs">
                        {(bid.requested_power_kw || bid.requested_amount_kwh).toFixed(2)} kW × {(bid.duration_hours || 1).toFixed(2)} h · {Math.round(bid.requested_units || bid.requested_amount_kwh * 100)} units @ ₹{bid.offered_price_per_kwh.toFixed(2)}/kWh
                      </span>
                      <Badge variant={bid.status === 'pending' ? 'pending' : bid.status === 'accepted' ? 'executed' : 'rejected'}>
                        {bid.status}
                      </Badge>
                    </div>
                    {bid.status === 'pending' && (
                      <div className="bid-actions">
                        <Button
                          variant="primary"
                          className="btn-sm"
                          onClick={() => handleRespondBid(bid.bid_id, 'accept')}
                          disabled={isResponding}
                        >
                          Accept
                        </Button>
                        <Button
                          variant="danger"
                          className="btn-sm"
                          onClick={() => handleRespondBid(bid.bid_id, 'reject')}
                          disabled={isResponding}
                        >
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Feasibility Result */}
          {tradeResult && (
            <Card
              title="Trade Result"
              className={`feasibility-result ${tradeResult.status}`}
            >
              <div className="flex justify-between items-center mb-md">
                <Badge variant={tradeResult.status === 'executed' ? 'executed' : tradeResult.status === 'partial_fill' ? 'partial' : 'rejected'}>
                  {tradeResult.status.replace('_', ' ')}
                </Badge>
                <Button variant="ghost" className="btn-sm" onClick={() => setTradeResult(null)}>Dismiss</Button>
              </div>
              <p className="text-sm mb-md">{tradeResult.message}</p>
              {tradeResult.amount_kwh != null && (
                <p className="text-mono text-sm text-muted">
                  {tradeResult.amount_kwh.toFixed(3)} kWh @ ₹{tradeResult.price_per_kwh?.toFixed(2)}/kWh
                  = ₹{tradeResult.total_price?.toFixed(2)}
                </p>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
