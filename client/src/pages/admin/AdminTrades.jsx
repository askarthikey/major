import { useState, useEffect } from 'react';
import { getAllTrades } from '../../services/api';
import { timeAgo } from '../../utils/formatters';

function getStatusBadgeClass(status) {
  if (status === 'executed' || status === 'completed') return 'executed';
  if (status === 'partial_fill' || status === 'under_delivered') return 'partial';
  if (status === 'scheduled' || status === 'delivering') return 'pending';
  return 'rejected';
}

export default function AdminTrades() {
  const [trades, setTrades] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', limit: 100, skip: 0 });
  const [expandedTrade, setExpandedTrade] = useState(null);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const result = await getAllTrades(filters);
      setTrades(result.trades || []);
      setTotal(result.total || 0);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTrades(); }, [filters.status]);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">🔄 All Trades ({total})</span>
        <div className="flex gap-sm items-center">
          <select
            className="form-input"
            style={{ width: 'auto', padding: '6px 10px', fontSize: '0.8rem' }}
            value={filters.status}
            onChange={e => setFilters(f => ({ ...f, status: e.target.value, skip: 0 }))}
          >
            <option value="">All Statuses</option>
            <option value="executed">Executed</option>
            <option value="completed">Completed</option>
            <option value="partial_fill">Partial Fill</option>
            <option value="under_delivered">Under Delivered</option>
            <option value="rejected">Rejected</option>
            <option value="scheduled">Scheduled</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="loading-overlay"><div className="spinner"></div></div>
      ) : trades.length === 0 ? (
        <p className="text-muted" style={{ padding: '32px 0', textAlign: 'center' }}>No trades found.</p>
      ) : (
        <div className="trade-table-container">
          <table className="trade-table">
            <thead>
              <tr>
                <th>Trade ID</th>
                <th>Time</th>
                <th>Seller → Buyer</th>
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
                const efficiency = scheduled > 0 && trade.status !== 'rejected'
                  ? ((delivered / scheduled) * 100) : null;
                const hasDelivery = !!trade.delivery;
                const isExpanded = expandedTrade === trade.trade_id;

                return (
                  <>
                    <tr
                      key={trade.trade_id}
                      className={trade.status === 'rejected' ? 'row-rejected' : ''}
                      onClick={() => hasDelivery && setExpandedTrade(isExpanded ? null : trade.trade_id)}
                      style={{ cursor: hasDelivery ? 'pointer' : 'default' }}
                    >
                      <td className="text-mono text-xs">{trade.trade_id}</td>
                      <td className="text-muted text-xs">{timeAgo(trade.timestamp)}</td>
                      <td>Bus {trade.seller_bus} → {trade.buyer_bus}</td>
                      <td className="text-mono">{scheduled?.toFixed(3)} kWh</td>
                      <td className="text-mono" style={{
                        color: trade.status === 'under_delivered' ? 'var(--accent-amber)' :
                               (trade.status === 'completed' || trade.status === 'executed') ? 'var(--accent-green)' :
                               trade.status === 'rejected' ? 'var(--accent-red)' : 'inherit'
                      }}>
                        {trade.status === 'rejected' ? '0.000' : delivered?.toFixed(3)} kWh
                      </td>
                      <td className="text-mono">
                        {efficiency != null ? (
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
                        <td colSpan={9}>
                          <div className="delivery-detail-panel">
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                              {/* Left: Pipeline */}
                              <div className="delivery-pipeline">
                                {trade.original_amount_kwh != null && (
                                  <div className="delivery-row">
                                    <span className="delivery-label">📋 Original Request</span>
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
                                <div className="delivery-row">
                                  <span className="delivery-label">📉 Discrepancy</span>
                                  <span className="text-mono text-muted">{trade.delivery.discrepancy_kwh?.toFixed(4)} kWh ({trade.delivery.discrepancy_percent?.toFixed(2)}%)</span>
                                </div>
                              </div>

                              {/* Right: Delivery details */}
                              <div>
                                <div className="delivery-pipeline">
                                  <div className="delivery-row">
                                    <span className="delivery-label">🔌 Dispatch Power</span>
                                    <span className="text-mono">{trade.delivery.dispatch_power_kw?.toFixed(1)} kW</span>
                                  </div>
                                  <div className="delivery-row">
                                    <span className="delivery-label">⏱️ Duration</span>
                                    <span className="text-mono">{trade.delivery.delivery_duration_hours?.toFixed(2)} hours</span>
                                  </div>
                                  <div className="delivery-row">
                                    <span className="delivery-label">☀️ Solar Factor</span>
                                    <span className="text-mono">{(trade.delivery.avg_solar_factor * 100)?.toFixed(1)}%</span>
                                  </div>
                                  <div className="delivery-row">
                                    <span className="delivery-label">⚙️ Inverter Eff.</span>
                                    <span className="text-mono">{(trade.delivery.avg_inverter_efficiency * 100)?.toFixed(1)}%</span>
                                  </div>
                                  <div className="delivery-row">
                                    <span className="delivery-label">🔗 Line Loss</span>
                                    <span className="text-mono">{(trade.delivery.avg_line_loss_factor * 100)?.toFixed(1)}%</span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Timeline bars */}
                            {trade.delivery?.intervals?.length > 0 && (
                              <div className="delivery-timeline" style={{ marginTop: 14 }}>
                                <span className="text-xs text-muted" style={{ marginBottom: 4, display: 'block' }}>Delivery Timeline ({trade.delivery.num_intervals} intervals)</span>
                                <div className="delivery-timeline-bars">
                                  {trade.delivery.intervals.map((iv, i) => {
                                    const pct = scheduled > 0 ? (iv.actual_kwh / (scheduled / trade.delivery.intervals.length)) * 100 : 0;
                                    return (
                                      <div
                                        key={i}
                                        className="delivery-timeline-bar"
                                        title={`Interval ${i + 1}: ${iv.actual_kwh?.toFixed(3)} kWh | Solar: ${(iv.solar_factor * 100).toFixed(1)}% | Inverter: ${(iv.inverter_eff * 100).toFixed(1)}% | Line: ${(iv.line_loss * 100).toFixed(1)}%`}
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
