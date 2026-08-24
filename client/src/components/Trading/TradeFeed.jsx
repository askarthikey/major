import { formatKWh, formatPrice } from '../../utils/formatters';

export default function TradeFeed({ trades }) {
  if (!trades || trades.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">🔄 Live Trade Feed</span>
          <span className="text-xs text-muted">0 trades</span>
        </div>
        <div className="loading-overlay" style={{ padding: 'var(--space-xl)' }}>
          <span className="text-muted">No trades yet. Start the simulation!</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ maxHeight: 500, display: 'flex', flexDirection: 'column' }}>
      <div className="card-header">
        <span className="card-title">🔄 Live Trade Feed</span>
        <span className="text-xs text-muted">{trades.length} trades</span>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {trades.map((trade, i) => {
          const status = trade.status || 'pending';
          const statusEmoji = status === 'executed' ? '✅'
            : status === 'rejected' ? '❌'
            : status === 'partial_fill' ? '⚠️'
            : '⏳';

          return (
            <div key={trade.trade_id || i} className="trade-item">
              {/* Status indicator */}
              <div style={{
                width: 4,
                height: 36,
                borderRadius: 'var(--radius-full)',
                background: status === 'executed' ? 'var(--accent-green)'
                  : status === 'rejected' ? 'var(--accent-red)'
                  : status === 'partial_fill' ? 'var(--accent-amber)'
                  : 'var(--accent-blue)',
                flexShrink: 0,
              }} />

              {/* Trade info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="flex items-center gap-sm">
                  <span className="text-sm" style={{ fontWeight: 600 }}>
                    {trade.seller || trade.seller_household_id || '?'}
                  </span>
                  <span className="text-muted">→</span>
                  <span className="text-sm" style={{ fontWeight: 600 }}>
                    {trade.buyer || trade.buyer_household_id || '?'}
                  </span>
                </div>
                <div className="flex items-center gap-md mt-sm">
                  <span className="text-xs text-muted">
                    ⚡ {formatKWh(trade.amount_kwh || 0)}
                  </span>
                  <span className="text-xs text-muted">
                    💰 {formatPrice(trade.price || trade.price_per_kwh || 0)}/kWh
                  </span>
                </div>
              </div>

              {/* Status badge */}
              <div className="flex flex-col items-center gap-sm" style={{ flexShrink: 0 }}>
                <span className={`badge ${status === 'partial_fill' ? 'partial' : status}`}>
                  {statusEmoji} {status === 'partial_fill' ? 'Partial' : status}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
