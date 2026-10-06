import { useState, useEffect } from 'react';
import { getAdminStats } from '../../services/api';

export default function AdminStats() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="loading-overlay"><div className="spinner"></div></div>;
  }

  if (!stats) {
    return <div className="card"><p className="text-muted" style={{ padding: 16 }}>Unable to load stats.</p></div>;
  }

  const rejectionPct = (stats.rejection_rate * 100).toFixed(1);

  return (
    <div className="dashboard-grid">
      {/* Stats Cards */}
      <div className="stats-row">
        <div className="stat-card green">
          <div className="stat-label">Total Trades</div>
          <div className="stat-value">{stats.total_trades}</div>
          <div className="stat-subtitle">
            {stats.total_executed} completed, {stats.total_partial} partial, {stats.total_rejected} rejected
            {stats.total_under_delivered > 0 && `, ${stats.total_under_delivered} under-delivered`}
          </div>
          <div className="stat-icon">🔄</div>
        </div>

        <div className="stat-card blue">
          <div className="stat-label">Energy Delivered</div>
          <div className="stat-value">{stats.total_energy_kwh?.toFixed(1)}</div>
          <div className="stat-subtitle">
            {stats.total_scheduled_kwh ? `of ${stats.total_scheduled_kwh?.toFixed(1)} kWh scheduled` : 'kWh total'}
          </div>
          <div className="stat-icon">⚡</div>
        </div>

        <div className="stat-card amber">
          <div className="stat-label">Revenue</div>
          <div className="stat-value">₹{stats.total_revenue?.toFixed(2)}</div>
          <div className="stat-subtitle">Avg ₹{stats.avg_price?.toFixed(2)}/kWh</div>
          <div className="stat-icon">💰</div>
        </div>

        <div className="stat-card red">
          <div className="stat-label">Violations Prevented</div>
          <div className="stat-value">{stats.violations_prevented}</div>
          <div className="stat-subtitle">{rejectionPct}% rejection rate</div>
          <div className="stat-icon">🛡️</div>
        </div>
      </div>

      {/* Headline Metric */}
      <div className="card card-headline">
        <div className="headline-metric">
          <div className="headline-value">{stats.violations_prevented}</div>
          <div className="headline-label">
            trades would have caused grid violations without the GNN feasibility gate
          </div>
        </div>
        <div className="headline-bar">
          <div className="headline-bar-fill" style={{ width: `${Math.min(100, stats.rejection_rate * 100)}%` }}></div>
        </div>
        <div className="flex justify-between text-xs text-muted mt-sm">
          <span>Feasibility Rejection Rate</span>
          <span className="text-mono">{rejectionPct}%</span>
        </div>
      </div>

      {/* Secondary Stats */}
      <div className="stats-row">
        <div className="stat-card green">
          <div className="stat-label">Active Listings</div>
          <div className="stat-value">{stats.active_listings}</div>
          <div className="stat-icon">📋</div>
        </div>

        <div className="stat-card blue">
          <div className="stat-label">Pending Bids</div>
          <div className="stat-value">{stats.pending_bids}</div>
          <div className="stat-icon">📨</div>
        </div>

        <div className="stat-card green">
          <div className="stat-label">Registered Sellers</div>
          <div className="stat-value">{stats.registered_sellers}</div>
          <div className="stat-icon">🏠</div>
        </div>

        <div className="stat-card blue">
          <div className="stat-label">Registered Buyers</div>
          <div className="stat-value">{stats.registered_buyers}</div>
          <div className="stat-icon">🛒</div>
        </div>
      </div>
    </div>
  );
}
