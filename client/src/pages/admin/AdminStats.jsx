import React from 'react';
import { useAdminStats } from '../../hooks/api';
import { Card, PageIntro, StatCard, ProgressBar } from '../../components/ui';

export default function AdminStats() {
  const { data: stats, isLoading } = useAdminStats();

  if (isLoading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <span className="text-muted">Loading Analytics...</span>
      </div>
    );
  }

  if (!stats) {
    return (
      <Card>
        <p className="text-muted text-sm text-center" style={{ padding: '32px 0' }}>
          Unable to load statistics. Please check your connection.
        </p>
      </Card>
    );
  }

  const rejectionPct = (stats.rejection_rate * 100).toFixed(1);

  return (
    <div className="dashboard-grid">
      <PageIntro
        eyebrow="Network intelligence"
        title="Analytics"
        description="A clear read on market activity, energy movement, and the AI safety layer."
      />
      {/* Primary KPI Row */}
      <div className="stats-row">
        <StatCard label="Total trades" value={stats.total_trades} detail={
          <>
            <span className="text-green">{stats.total_executed} exec</span> •
            <span className="text-amber"> {stats.total_partial} partial</span> •
            <span className="text-red"> {stats.total_rejected} rej</span>
          </>
        } />
        <StatCard label="Energy traded" value={stats.total_energy_kwh?.toFixed(1)} detail="kWh total volume" accent="blue" />
        <StatCard label="Total revenue" value={`₹${stats.total_revenue?.toFixed(2)}`} detail={`Avg ₹${stats.avg_price?.toFixed(2)}/kWh`} accent="amber" />
        <StatCard label="Violations prevented" value={stats.violations_prevented} detail={`${rejectionPct}% system rejection rate`} />
      </div>

      {/* Safety Analysis Section */}
      <Card title="GNN Feasibility Impact">
        <div className="flex flex-col gap-md">
          <div className="headline-metric">
            <div className="headline-value">{stats.violations_prevented}</div>
            <div className="headline-label">
              Trades prevented by the AI safety gate to ensure grid stability
            </div>
          </div>

          <ProgressBar value={stats.rejection_rate * 100} label="System stability guard (rejection rate)" />
        </div>
      </Card>

      {/* Network Growth Row */}
      <div className="stats-row">
        <StatCard label="Active listings" value={stats.active_listings} />
        <StatCard label="Pending bids" value={stats.pending_bids} />
        <StatCard label="Registered sellers" value={stats.registered_sellers} />
        <StatCard label="Registered buyers" value={stats.registered_buyers} />
      </div>
    </div>
  );
}
