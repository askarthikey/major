import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import GridGraph from '../../components/Grid/GridGraph';
import {
  useGridState,
  useListings,
  useMyBids,
  usePlaceBid,
  usePreviewBid
} from '../../hooks/api';
import { Card, Button, Input, Badge, PageIntro, StatCard } from '../../components/ui';

export default function BuyerHome() {
  const { user } = useAuth();
  const { lastMessage } = useWebSocket();

  // Data from React Query
  const { data: gridState, isLoading: gridLoading } = useGridState();
  const { data: listings = [], isLoading: listingsLoading } = useListings();
  const { data: myBids = [], isLoading: bidsLoading } = useMyBids();
  const { mutate: placeBid, isPending: bidLoading } = usePlaceBid();
  const { mutateAsync: previewBid, isPending: previewLoading } = usePreviewBid();

  const [selectedListing, setSelectedListing] = useState(null);
  const [bidPower, setBidPower] = useState('');
  const [bidDuration, setBidDuration] = useState('');
  const [bidPrice, setBidPrice] = useState('');
  const [preview, setPreview] = useState(null);
  const [localError, setLocalError] = useState('');
  const [localSuccess, setLocalSuccess] = useState('');

  // Sync WebSocket updates with React Query cache
  useEffect(() => {
    if (lastMessage?.type === 'simulation_step' && lastMessage.data?.grid_state) {
      // In a real app, we'd use queryClient.setQueryData here
      // For now, we'll keep the UI responsive to WS
    }
  }, [lastMessage]);

  const handleSelectListing = (listing) => {
    setSelectedListing(listing);
    setBidPower((listing.power_kw || listing.amount_kwh_available).toString());
    setBidDuration((listing.duration_hours || 1).toString());
    setBidPrice(listing.asking_price_per_kwh.toString());
    setLocalError('');
    setLocalSuccess('');
    setPreview(null);
  };

  const handlePreview = async () => {
    if (!selectedListing) return;
    setLocalError('');
    try {
      setPreview(await previewBid({
        listingId: selectedListing.listing_id,
        powerKw: parseFloat(bidPower),
        durationHours: parseFloat(bidDuration),
      }));
    } catch (err) {
      setLocalError(err.message);
    }
  };

  const handlePlaceBid = async (e) => {
    e.preventDefault();
    if (!selectedListing) return;
    setLocalError('');
    setLocalSuccess('');

    try {
      await placeBid({
        listingId: selectedListing.listing_id,
        powerKw: parseFloat(bidPower),
        durationHours: parseFloat(bidDuration),
        pricePerKwh: parseFloat(bidPrice)
      });
      setLocalSuccess('Bid placed! You will be notified when the seller responds.');
      setSelectedListing(null);
    } catch (err) {
      setLocalError(err.message);
    }
  };

  if (gridLoading || listingsLoading || bidsLoading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <span className="text-muted">Loading Marketplace...</span>
      </div>
    );
  }

  return (
    <div className="dashboard-grid">
      <PageIntro
        eyebrow={`Buyer workspace / Bus ${user?.bus_id ?? '—'}`}
        title="Find the right energy."
        description="Explore live offers from your neighborhood and place a bid with confidence."
      />
      <div className="stats-row">
        <StatCard label="Available offers" value={listings.length} detail="Open listings nearby" />
        <StatCard label="My bids" value={myBids.length} detail="Offers in your pipeline" accent="amber" />
        <StatCard label="Network status" value="Stable" detail="Grid-aware matching active" accent="blue" />
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
              listings={listings}
              role="buyer"
              onBusClick={(busId) => {
                const listing = listings.find(l => l.bus_id === busId);
                if (listing) handleSelectListing(listing);
              }}
            />
          </Card>

          <Card title={`Available Listings (${listings.length})`}>
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
                        <span className="listing-stat-value text-mono">{(listing.power_kw || listing.amount_kwh_available).toFixed(1)}</span>
                        <span className="listing-stat-label">kW available</span>
                      </div>
                      <div className="listing-stat">
                        <span className="listing-stat-value text-mono">{Math.round(listing.units_available || listing.amount_kwh_available * 100)}</span>
                        <span className="listing-stat-label">10 Wh units</span>
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
          </Card>
        </div>

        <div className="flex flex-col gap-lg">
          {selectedListing ? (
            <Card
              title="Place Bid"
              className="card-highlight"
            >
              <div className="flex justify-between items-center mb-md">
                <p className="text-sm text-muted">
                  Bidding on <strong className="text-primary">{selectedListing.seller_name}</strong> (Bus {selectedListing.bus_id})
                </p>
                <Button variant="ghost" className="btn-sm" onClick={() => setSelectedListing(null)}>×</Button>
              </div>

              <form onSubmit={handlePlaceBid} className="flex flex-col gap-md">
                <Input
                  label="Power (kW)"
                  type="number"
                  value={bidPower}
                  onChange={e => { setBidPower(e.target.value); setPreview(null); }}
                  step="0.1"
                  min="0.1"
                  max={selectedListing.power_kw || selectedListing.amount_kwh_available}
                  required
                />
                <Input
                  label="Duration (hours)"
                  type="number"
                  value={bidDuration}
                  onChange={e => { setBidDuration(e.target.value); setPreview(null); }}
                  step="0.25"
                  min="0.25"
                  max="24"
                  required
                />
                <span className="text-xs text-muted text-right">
                  Requested: {(parseFloat(bidPower || 0) * parseFloat(bidDuration || 0)).toFixed(2)} kWh · {Math.round(parseFloat(bidPower || 0) * parseFloat(bidDuration || 0) * 100)} units
                </span>

                <Input
                  label="Your Price Offer (₹/kWh)"
                  type="number"
                  value={bidPrice}
                  onChange={e => setBidPrice(e.target.value)}
                  step="0.01"
                  min="0.01"
                  required
                />
                <span className="text-xs text-muted text-right">Asking: ₹{selectedListing.asking_price_per_kwh.toFixed(2)}/kWh</span>

                <Button type="button" variant="secondary" onClick={handlePreview} disabled={previewLoading}>
                  {previewLoading ? 'Checking grid…' : 'Check feasible flow'}
                </Button>
                {preview && (
                  <div className={`alert ${preview.feasible ? 'alert-success' : 'alert-error'}`}>
                    {preview.feasible
                      ? `Feasible at ${preview.feasible.power_kw.toFixed(2)} kW for ${preview.feasible.duration_hours.toFixed(2)} h (${preview.feasible.units} units).`
                      : 'No safe transfer is available for this request right now.'}
                    <div className="text-xs mt-sm">
                      Confidence {(preview.confidence * 100).toFixed(1)}% · Capacity is advisory and checked again on acceptance.
                    </div>
                  </div>
                )}
                <Button
                  type="submit"
                  variant="primary"
                  className="mt-md"
                  disabled={bidLoading || (preview && !preview.feasible)}
                >
                  {bidLoading ? (
                    <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Placing bid...</>
                  ) : 'Place Bid'}
                </Button>
              </form>
            </Card>
          ) : (
            <Card title="Place Bid">
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>
                Click on a seller's house on the map or a listing card to place a bid.
              </p>
            </Card>
          )}

          <Card title={`My Bids (${myBids.length})`}>
            {myBids.length === 0 ? (
              <p className="text-muted text-sm" style={{ padding: '16px 0' }}>No bids placed yet.</p>
            ) : (
              <div className="bid-list">
                {myBids.map(bid => (
                  <div key={bid.bid_id} className="bid-item">
                    <div className="bid-info">
                      <span className="text-sm">Listing: Bus {bid.bus_id || '?'}</span>
                      <span className="text-mono text-xs">
                        {bid.requested_amount_kwh?.toFixed(2)} kWh @ ₹{bid.offered_price_per_kwh?.toFixed(2)}
                      </span>
                    </div>
                    <Badge variant={
                      bid.status === 'pending' ? 'pending' :
                      bid.status === 'accepted' ? 'executed' :
                      bid.status === 'feasibility_partial' ? 'partial' : 'rejected'
                    }>
                      {bid.status?.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
