export function formatKWh(value) {
  if (value >= 1000) return `${(value / 1000).toFixed(1)} MWh`;
  return `${value.toFixed(2)} kWh`;
}

export function formatPrice(value) {
  return `₹${value.toFixed(2)}`;
}

export function formatPercent(value) {
  return `${value.toFixed(1)}%`;
}

export function formatVoltage(pu) {
  return `${(pu * 100).toFixed(2)}%`;
}

export function getVoltageColor(pu) {
  const dev = Math.abs(pu - 1.0);
  if (dev <= 0.02) return 'var(--accent-green)';
  if (dev <= 0.04) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}

export function getLoadingColor(pct) {
  if (pct <= 60) return 'var(--accent-green)';
  if (pct <= 85) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}

export function getStatusColor(status) {
  switch (status) {
    case 'executed': return 'var(--accent-green)';
    case 'rejected': return 'var(--accent-red)';
    case 'partial_fill': return 'var(--accent-amber)';
    default: return 'var(--accent-blue)';
  }
}

export function timeAgo(date) {
  const seconds = Math.floor((new Date() - new Date(date)) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}
