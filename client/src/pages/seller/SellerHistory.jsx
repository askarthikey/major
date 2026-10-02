import { useState, useEffect } from 'react';
import { getMyTrades } from '../../services/api';
import { formatKWh, formatPrice, timeAgo } from '../../utils/formatters';

export default function SellerHistory() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

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
                  <td>Bus {trade.buyer_bus} → Bus {trade.seller_bus}</td>
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
