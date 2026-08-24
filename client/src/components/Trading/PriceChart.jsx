import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-medium)',
      borderRadius: 'var(--radius-md)',
      padding: '8px 12px',
      fontSize: '0.75rem',
    }}>
      <p style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color }}>
          {entry.name}: ₹{Number(entry.value).toFixed(2)}
        </p>
      ))}
    </div>
  );
};

export default function PriceChart({ priceHistory }) {
  // If no data, show placeholder
  if (!priceHistory || priceHistory.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">📈 Clearing Price History</span>
        </div>
        <div className="loading-overlay" style={{ height: 250 }}>
          <span className="text-muted">Price data will appear as trades execute</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">📈 Clearing Price History</span>
        <span className="text-xs text-muted">{priceHistory.length} data points</span>
      </div>

      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <AreaChart data={priceHistory} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border-subtle)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--border-subtle)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `₹${v}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="avgPrice"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#priceGradient)"
              name="Avg Price"
              dot={false}
              activeDot={{ r: 4, fill: '#10b981', stroke: 'var(--bg-primary)', strokeWidth: 2 }}
            />
            {priceHistory[0]?.maxPrice !== undefined && (
              <Line
                type="monotone"
                dataKey="maxPrice"
                stroke="#f59e0b"
                strokeWidth={1}
                strokeDasharray="4 4"
                name="Max Price"
                dot={false}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
