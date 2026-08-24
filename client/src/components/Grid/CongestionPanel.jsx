import { formatPercent } from '../../utils/formatters';

export default function CongestionPanel({ gridState }) {
  const buses = gridState?.buses || [];
  const lines = gridState?.lines || [];

  const voltageViolations = buses.filter(b => b.is_violation);
  const lineViolations = lines.filter(l => l.is_violation);
  const maxLoading = lines.length > 0 ? Math.max(...lines.map(l => l.loading_percent || 0)) : 0;
  const maxVDev = buses.length > 0 ? Math.max(...buses.map(b => Math.abs((b.voltage_pu || 1) - 1))) : 0;

  // Sort lines by loading (highest first)
  const sortedLines = [...lines].sort((a, b) => (b.loading_percent || 0) - (a.loading_percent || 0));

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">🔌 Grid Congestion</span>
        <span className={`badge ${voltageViolations.length + lineViolations.length > 0 ? 'rejected' : 'executed'}`}>
          {voltageViolations.length + lineViolations.length > 0
            ? `${voltageViolations.length + lineViolations.length} Violations`
            : 'All Clear'}
        </span>
      </div>

      {/* Summary */}
      <div className="flex gap-md mb-md" style={{ flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 100 }}>
          <div className="text-xs text-muted">Max Line Loading</div>
          <div className="text-mono" style={{
            fontSize: '1.2rem',
            fontWeight: 700,
            color: maxLoading > 100 ? 'var(--accent-red)' : maxLoading > 80 ? 'var(--accent-amber)' : 'var(--accent-green)',
          }}>
            {formatPercent(maxLoading)}
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 100 }}>
          <div className="text-xs text-muted">Max Voltage Dev</div>
          <div className="text-mono" style={{
            fontSize: '1.2rem',
            fontWeight: 700,
            color: maxVDev > 0.05 ? 'var(--accent-red)' : maxVDev > 0.03 ? 'var(--accent-amber)' : 'var(--accent-green)',
          }}>
            ±{(maxVDev * 100).toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Line loading bars */}
      <div className="text-xs text-muted mb-md" style={{ fontWeight: 600 }}>
        Line Loading (Top 6)
      </div>
      <div className="flex flex-col gap-sm">
        {sortedLines.slice(0, 6).map((line, i) => {
          const loading = line.loading_percent || 0;
          const barColor = loading > 100
            ? 'var(--accent-red)'
            : loading > 80
            ? 'var(--accent-amber)'
            : 'var(--accent-green)';

          return (
            <div key={line.line_id ?? i}>
              <div className="flex justify-between items-center" style={{ marginBottom: 2 }}>
                <span className="text-xs text-muted">
                  {line.name || `Line ${line.line_id}`}
                </span>
                <span className="text-xs text-mono" style={{ color: barColor }}>
                  {formatPercent(loading)}
                </span>
              </div>
              <div style={{
                width: '100%',
                height: 6,
                background: 'var(--bg-tertiary)',
                borderRadius: 'var(--radius-full)',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${Math.min(100, loading)}%`,
                  height: '100%',
                  background: barColor,
                  borderRadius: 'var(--radius-full)',
                  transition: 'width 0.5s ease, background 0.3s ease',
                }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Violations list */}
      {(voltageViolations.length > 0 || lineViolations.length > 0) && (
        <div className="mt-md" style={{
          padding: 'var(--space-sm)',
          background: 'var(--accent-red-dim)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
        }}>
          <div className="text-xs" style={{ color: 'var(--accent-red)', fontWeight: 600, marginBottom: 4 }}>
            ⚠ Active Violations
          </div>
          {voltageViolations.map(b => (
            <div key={b.bus_id} className="text-xs text-muted">
              Bus {b.bus_id} ({b.name}): {(b.voltage_pu * 100).toFixed(2)}% voltage
            </div>
          ))}
          {lineViolations.map(l => (
            <div key={l.line_id} className="text-xs text-muted">
              Line {l.line_id}: {formatPercent(l.loading_percent)} loading
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
