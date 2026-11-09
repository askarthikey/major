import { useState, useEffect } from 'react';
import { getMyTrades, getMyBids } from '../../services/api';
import { timeAgo } from '../../utils/formatters';
import { PageIntro } from '../../components/ui';

export default function BuyerHistory() {
  const [trades, setTrades] = useState([]);
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('bids');

  useEffect(() => {
    Promise.all([
      getMyTrades(100).catch(() => []),
      getMyBids().catch(() => []),
    ]).then(([t, b]) => {
      setTrades(t);
      setBids(b);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="loading-overlay"><div className="spinner"></div></div>;
  }

  return (
    <div className="dashboard-grid">
      <PageIntro eyebrow="Buyer workspace" title="Bids & trades" description="Follow your offers from first click to completed exchange." />
      <div className="card">
      <div className="card-header">
        <span className="card-title">📜 My Bids & Trades</span>
        <div className="tab-group">
          <button className={`tab-btn ${tab === 'bids' ? 'active' : ''}`} onClick={() => setTab('bids')}>
            Bids ({bids.length})
          </button>
          <button className={`tab-btn ${tab === 'trades' ? 'active' : ''}`} onClick={() => setTab('trades')}>
            Trades ({trades.length})
          </button>
          </div>
        </div>
      </div>

      {tab === 'bids' && (
        bids.length === 0 ? (
          <p className="text-muted" style={{ padding: '32px 0', textAlign: 'center' }}>No bids placed yet.</p>
        ) : (
          <div className="trade-table-container">
            <table className="trade-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Listing Bus</th>
                  <th>Amount</th>
                  <th>Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {bids.map(bid => (
                  <tr key={bid.bid_id}>
                    <td className="text-muted text-xs">{timeAgo(bid.created_at)}</td>
                    <td>Bus {bid.bus_id || '?'}</td>
                    <td className="text-mono">{bid.requested_amount_kwh?.toFixed(2)} kWh</td>
                    <td className="text-mono">₹{bid.offered_price_per_kwh?.toFixed(2)}</td>
                    <td>
                      <span className={`badge ${bid.status === 'pending' ? 'pending' : bid.status === 'accepted' ? 'executed' : 'rejected'}`}>
                        {bid.status?.replace(/_/g, ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === 'trades' && (
        trades.length === 0 ? (
          <p className="text-muted" style={{ padding: '32px 0', textAlign: 'center' }}>No completed trades yet.</p>
        ) : (
          <div className="trade-table-container">
            <table className="trade-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Route</th>
                  <th>Amount</th>
                  <th>Price</th>
                  <th>Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(trade => (
                  <tr key={trade.trade_id}>
                    <td className="text-muted text-xs">{timeAgo(trade.timestamp)}</td>
                    <td>Bus {trade.seller_bus} → Bus {trade.buyer_bus}</td>
                    <td className="text-mono">{trade.amount_kwh?.toFixed(3)} kWh</td>
                    <td className="text-mono">₹{trade.price_per_kwh?.toFixed(2)}</td>
                    <td className="text-mono">₹{trade.total_price?.toFixed(2)}</td>
                    <td>
                      <span className={`badge ${trade.status === 'executed' ? 'executed' : trade.status === 'partial_fill' ? 'partial' : 'rejected'}`}>
                        {trade.status?.replace('_', ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
