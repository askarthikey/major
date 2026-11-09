import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import GridGraph from '../../components/Grid/GridGraph';
import CongestionPanel from '../../components/Grid/CongestionPanel';
import AISafetyStats from '../../components/Grid/AISafetyStats';
import { useGridState } from '../../hooks/api';
import { Card, PageIntro } from '../../components/ui';

export default function AdminGrid() {
  const { lastMessage } = useWebSocket();
  const { data: gridState, isLoading: gridLoading } = useGridState();

  const [safetyStats, setSafetyStats] = useState({
    avg_latency: '0.21',
    violations_prevented: 0,
    safety_rate: '98.5'
  });

  useEffect(() => {
    if (lastMessage?.type === 'simulation_step' && lastMessage.data?.grid_state) {
      // The gridState from React Query will update when simulation steps are triggered via mutations
    }

    if (lastMessage?.type === 'safety_stats') {
      setSafetyStats(lastMessage.data);
    }
  }, [lastMessage]);

  if (gridLoading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <span className="text-muted">Loading Admin Grid...</span>
      </div>
    );
  }

  return (
    <div className="dashboard-grid">
      <PageIntro
        eyebrow="Control room / live"
        title="Grid state"
        description="Watch the feeder breathe in real time. Every trade is measured against the network before it moves."
      />
      <div className="main-grid">
        <div className="flex flex-col gap-lg">
          <AISafetyStats stats={safetyStats} />

          <Card title="Real-time Grid Topology">
            <GridGraph gridState={gridState} role="admin" />
          </Card>

          <Card title="Visual Legend">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-lg">
              <div className="space-y-sm">
                <h4 className="text-xs text-muted uppercase font-bold mb-sm tracking-widest">Bus Voltage</h4>
                <div className="flex items-center gap-sm text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Normal (±2%)
                </div>
                <div className="flex items-center gap-sm text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span> Warning (±2-4%)
                </div>
                <div className="flex items-center gap-sm text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span> Violation (±5%+)
                </div>
              </div>
              <div className="space-y-sm">
                <h4 className="text-xs text-muted uppercase font-bold mb-sm tracking-widest">Line Loading</h4>
                <div className="flex items-center gap-sm text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Normal (&lt;60%)
                </div>
                <div className="flex items-center gap-sm text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span> Warning (60-85%)
                </div>
                <div className="flex items-center gap-sm text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span> Overloaded (&gt;85%)
                </div>
              </div>
            </div>
          </Card>
        </div>

        <div className="flex flex-col gap-lg">
          <CongestionPanel gridState={gridState} />
        </div>
      </div>
    </div>
  );
}
