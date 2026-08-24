import { formatKWh, formatPrice } from '../../utils/formatters';

export default function StatsCards({ stats }) {
  const cards = [
    {
      label: 'Total Energy Traded',
      value: formatKWh(stats.totalEnergyKwh || 0),
      icon: '⚡',
      color: 'green',
      subtitle: `${stats.totalTradesExecuted || 0} trades executed`,
    },
    {
      label: 'Violations Prevented',
      value: stats.violationsPrevented || 0,
      icon: '🛡️',
      color: 'amber',
      subtitle: `${stats.totalTradesRejected || 0} trades blocked`,
    },
    {
      label: 'Total Revenue',
      value: formatPrice(stats.totalRevenue || 0),
      icon: '💰',
      color: 'blue',
      subtitle: `Avg ₹${(stats.avgPrice || 0).toFixed(2)}/kWh`,
    },
    {
      label: 'Grid Health',
      value: stats.gridHealthy ? 'Healthy' : 'Warning',
      icon: stats.gridHealthy ? '✅' : '⚠️',
      color: stats.gridHealthy ? 'green' : 'red',
      subtitle: `${stats.voltageViolations || 0} violations active`,
    },
  ];

  return (
    <div className="stats-row">
      {cards.map((card, i) => (
        <div key={i} className={`stat-card ${card.color}`}>
          <span className="stat-icon">{card.icon}</span>
          <div className="stat-label">{card.label}</div>
          <div className="stat-value">{card.value}</div>
          <div className="stat-subtitle">{card.subtitle}</div>
        </div>
      ))}
    </div>
  );
}
