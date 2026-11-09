import React, { useState } from 'react';
import { useAllTrades } from '../../hooks/api';
import { timeAgo } from '../../utils/formatters';
import { Card, Table, Badge, PageIntro } from '../../components/ui';

export default function AdminTrades() {
  const [filters, setFilters] = useState({ status: '', limit: 100, skip: 0 });

  const { data: result, isLoading } = useAllTrades(filters);
  const trades = result?.trades || [];
  const total = result?.total || 0;

  return (
    <div className="dashboard-grid">
      <PageIntro
        eyebrow="Market activity"
        title="Trade registry"
        description="Search and review every energy exchange recorded across the network."
      />
      <Card title={`Trade Registry (${total})`}>
        <div className="flex justify-between items-center mb-md">
          <p className="text-sm text-muted">Master log of all energy transactions across the grid.</p>
          <div className="flex items-center gap-sm">
            <span className="text-xs text-muted mr-sm">Filter by status:</span>
            <select
              className="form-input text-xs"
              style={{ width: 'auto', padding: '4px 8px' }}
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

        {isLoading ? (
          <div className="loading-overlay" style={{ padding: '48px 0' }}>
            <div className="spinner"></div>
          </div>
        ) : trades.length === 0 ? (
          <p className="text-muted text-sm text-center" style={{ padding: '48px 0' }}>No trades found matching the selected criteria.</p>
        ) : (
          <Table
            headers={['Trade ID', 'Time', 'Seller Bus', 'Buyer Bus', 'Amount', 'Price', 'Total', 'Status']}
          >
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
                  <Badge variant={trade.status === 'executed' ? 'executed' : trade.status === 'partial_fill' ? 'partial' : 'rejected'}>
                    {trade.status?.replace('_', ' ')}
                  </Badge>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
