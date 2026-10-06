import { useState, useEffect } from 'react';
import { getMyTrades, getMyBids } from '../../services/api';
import { timeAgo } from '../../utils/formatters';

function getStatusBadgeClass(status) {
  if (status === 'executed' || status === 'completed') return 'executed';
  if (status === 'partial_fill') return 'partial';
  if (status === 'under_delivered') return 'partial';
  if (status === 'scheduled' || status === 'delivering' || status === 'pending') return 'pending';
  return 'rejected';
}

export default function BuyerHistory() {
  const [trades, setTrades] = useState([]);
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('bids');
  const [expandedTrade, setExpandedTrade] = useState(null);

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
                  <th>Requested</th>
                  <th>Scheduled</th>
                  <th>Delivered</th>
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
                    <td className="text-mono">
                      {bid.scheduled_amount_kwh != null ? `${bid.scheduled_amount_kwh.toFixed(2)} kWh` : '—'}
                    </td>
                    <td className="text-mono">
                      {bid.final_amount_kwh != null ? `${bid.final_amount_kwh.toFixed(2)} kWh` : '—'}
                    </td>
                    <td className="text-mono">₹{bid.offered_price_per_kwh?.toFixed(2)}</td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(bid.status)}`}>
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
                  <th>Scheduled</th>
                  <th>Delivered</th>
                  <th>Efficiency</th>
                  <th>Price</th>
                  <th>Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(trade => {
                  const scheduled = trade.scheduled_kwh ?? trade.amount_kwh;
                  const delivered = trade.actual_delivered_kwh ?? trade.amount_kwh;
                  const efficiency = scheduled > 0 ? ((delivered / scheduled) * 100) : null;
                  const hasDelivery = !!trade.delivery;
                  const isExpanded = expandedTrade === trade.trade_id;

                  return (
                    <>
                      <tr
                        key={trade.trade_id}
                        onClick={() => hasDelivery && setExpandedTrade(isExpanded ? null : trade.trade_id)}
                        style={{ cursor: hasDelivery ? 'pointer' : 'default' }}
                      >
                        <td className="text-muted text-xs">{timeAgo(trade.timestamp)}</td>
                        <td>Bus {trade.seller_bus} → Bus {trade.buyer_bus}</td>
                        <td className="text-mono">{scheduled?.toFixed(3)} kWh</td>
                        <td className="text-mono" style={{
                          color: trade.status === 'under_delivered' ? 'var(--accent-amber)' :
                                 (trade.status === 'completed' || trade.status === 'executed') ? 'var(--accent-green)' : 'inherit'
                        }}>
                          {delivered?.toFixed(3)} kWh
                        </td>
                        <td className="text-mono">
                          {efficiency != null && trade.status !== 'rejected' ? (
                            <span style={{ color: efficiency >= 98 ? 'var(--accent-green)' : 'var(--accent-amber)' }}>
                              {efficiency.toFixed(1)}%
                            </span>
                          ) : '—'}
                        </td>
                        <td className="text-mono">₹{trade.price_per_kwh?.toFixed(2)}</td>
                        <td className="text-mono">₹{trade.total_price?.toFixed(2)}</td>
                        <td>
                          <span className={`badge ${getStatusBadgeClass(trade.status)}`}>
                            {trade.status?.replace(/_/g, ' ')}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && hasDelivery && (
                        <tr key={`${trade.trade_id}-detail`} className="delivery-detail-row">
                          <td colSpan={8}>
                            <div className="delivery-detail-panel">
                              <div className="delivery-pipeline">
                                {trade.original_amount_kwh != null && (
                                  <div className="delivery-row">
                                    <span className="delivery-label">📋 Requested</span>
                                    <span className="text-mono">{trade.original_amount_kwh?.toFixed(3)} kWh</span>
                                  </div>
                                )}
                                <div className="delivery-row">
                                  <span className="delivery-label">✅ Scheduled</span>
                                  <span className="text-mono">{scheduled?.toFixed(3)} kWh</span>
                                </div>
                                <div className="delivery-row" style={{ fontWeight: 600 }}>
                                  <span className="delivery-label">⚡ Delivered</span>
                                  <span className="text-mono">{delivered?.toFixed(3)} kWh</span>
                                </div>
                              </div>

                              {/* Dispatch info */}
                              {trade.delivery && (
                                <div className="delivery-dispatch-info" style={{ marginTop: 8 }}>
                                  <span className="text-xs text-muted">
                                    Dispatch: {trade.delivery.dispatch_power_kw?.toFixed(1)} kW × {trade.delivery.delivery_duration_hours?.toFixed(2)}h
                                    {' | '}Solar: {(trade.delivery.avg_solar_factor * 100)?.toFixed(1)}%
                                    {' | '}Inverter: {(trade.delivery.avg_inverter_efficiency * 100)?.toFixed(1)}%
                                    {' | '}Line: {(trade.delivery.avg_line_loss_factor * 100)?.toFixed(1)}%
                                  </span>
                                </div>
                              )}

                              {/* Mini delivery timeline */}
                              {trade.delivery?.intervals?.length > 0 && (
                                <div className="delivery-timeline" style={{ marginTop: 12 }}>
                                  <span className="text-xs text-muted" style={{ marginBottom: 4, display: 'block' }}>Delivery Timeline</span>
                                  <div className="delivery-timeline-bars">
                                    {trade.delivery.intervals.map((iv, i) => {
                                      const pct = scheduled > 0 ? (iv.actual_kwh / (scheduled / trade.delivery.intervals.length)) * 100 : 0;
                                      return (
                                        <div
                                          key={i}
                                          className="delivery-timeline-bar"
                                          title={`Interval ${i + 1}: ${iv.actual_kwh?.toFixed(3)} kWh (${pct.toFixed(1)}% of target)`}
                                          style={{
                                            height: `${Math.min(100, Math.max(10, pct))}%`,
                                            background: pct >= 98 ? 'var(--accent-green)' : pct >= 90 ? 'var(--accent-amber)' : 'var(--accent-red)',
                                          }}
                                        />
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
