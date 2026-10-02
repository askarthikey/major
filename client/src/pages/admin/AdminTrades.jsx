import { useState, useEffect } from 'react';
import { getAllTrades } from '../../services/api';
import { timeAgo } from '../../utils/formatters';

export default function AdminTrades() {
  const [trades, setTrades] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', limit: 100, skip: 0 });

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
            <option value="partial_fill">Partial Fill</option>
            <option value="rejected">Rejected</option>
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
                <th>Seller Bus</th>
                <th>Buyer Bus</th>
                <th>Amount</th>
                <th>Price</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trades.map(trade => (
                <tr key={trade.trade_id} className={trade.status === 'rejected' ? 'row-rejected' : ''}>
                  <td className="text-mono text-xs">{trade.trade_id}</td>
                  <td className="text-muted text-xs">{timeAgo(trade.timestamp)}</td>
                  <td>Bus {trade.seller_bus}</td>
                  <td>Bus {trade.buyer_bus}</td>
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
      )}
    </div>
  );
}
