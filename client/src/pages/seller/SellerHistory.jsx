import { useState, useEffect } from 'react';
import { getMyTrades } from '../../services/api';
import { formatKWh, formatPrice, timeAgo } from '../../utils/formatters';

function getStatusBadgeClass(status) {
  if (status === 'executed' || status === 'completed') return 'executed';
  if (status === 'partial_fill') return 'partial';
  if (status === 'under_delivered') return 'partial';
  if (status === 'scheduled' || status === 'delivering') return 'pending';
  return 'rejected';
}

export default function SellerHistory() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedTrade, setExpandedTrade] = useState(null);

  useEffect(() => {
    getMyTrades(100)
      .then(setTrades)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="loading-overlay"><div className="spinner"></div></div>;
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">📜 Your Trade History</span>
        <span className="text-xs text-muted">{trades.length} trades</span>
      </div>

      {trades.length === 0 ? (
        <p className="text-muted" style={{ padding: '32px 0', textAlign: 'center' }}>
          No trades yet. Accept bids from buyers to start trading.
        </p>
      ) : (
        <div className="trade-table-container">
          <table className="trade-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Counterparty</th>
                <th>Scheduled</th>
                <th>Delivered</th>
                <th>Efficiency</th>
                <th>Price</th>
                <th>Revenue</th>
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
                      <td>Bus {trade.buyer_bus} → Bus {trade.seller_bus}</td>
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
                                  <span className="delivery-label">📋 Original Listed</span>
                                  <span className="text-mono">{trade.original_amount_kwh?.toFixed(3)} kWh</span>
                                </div>
                              )}
                              {trade.listing_original_kwh != null && (
                                <div className="delivery-row">
                                  <span className="delivery-label">🏷️ Listing Before</span>
                                  <span className="text-mono">{trade.listing_original_kwh?.toFixed(3)} kWh</span>
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
                              {trade.listing_remaining_kwh != null && (
                                <div className="delivery-row">
                                  <span className="delivery-label">📦 Remaining</span>
                                  <span className="text-mono text-muted">{trade.listing_remaining_kwh?.toFixed(3)} kWh</span>
                                </div>
                              )}
                            </div>

                            {/* Dispatch info */}
                            {trade.delivery && (
                              <div className="delivery-dispatch-info" style={{ marginTop: 10 }}>
                                <span className="text-xs text-muted">
                                  Dispatch: {trade.delivery.dispatch_power_kw?.toFixed(1)} kW × {trade.delivery.delivery_duration_hours?.toFixed(2)}h
                                  {' | '}Intervals: {trade.delivery.num_intervals}
                                  {' | '}Solar: {(trade.delivery.avg_solar_factor * 100)?.toFixed(1)}%
                                  {' | '}Inverter: {(trade.delivery.avg_inverter_efficiency * 100)?.toFixed(1)}%
                                  {' | '}Line: {(trade.delivery.avg_line_loss_factor * 100)?.toFixed(1)}%
                                </span>
                              </div>
                            )}

                            {/* Mini delivery timeline bar chart */}
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
      )}
    </div>
  );
}
