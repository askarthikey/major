import { useState, useEffect } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import GridGraph from '../../components/Grid/GridGraph';
import CongestionPanel from '../../components/Grid/CongestionPanel';
import { getGridState } from '../../services/api';

export default function AdminGrid() {
  const { lastMessage } = useWebSocket();
  const [gridState, setGridState] = useState(null);

  useEffect(() => {
    getGridState().then(setGridState).catch(() => {});
  }, []);

  useEffect(() => {
    if (lastMessage?.type === 'simulation_step' && lastMessage.data?.grid_state) {
      setGridState(lastMessage.data.grid_state);
    }
  }, [lastMessage]);

  return (
    <div className="dashboard-grid">
      <div className="main-grid">
        <div className="flex flex-col gap-lg">
          <GridGraph gridState={gridState} role="admin" />

          {/* Color Legend */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">🎨 Color Legend</span>
            </div>
            <div className="legend-grid">
              <div className="legend-section">
                <h4 className="text-xs text-muted" style={{ marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Bus Voltage</h4>
                <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent-green)' }}></span> Normal (±2%)</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent-amber)' }}></span> Warning (±2-4%)</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent-red)' }}></span> Violation (±5%+)</div>
              </div>
              <div className="legend-section">
                <h4 className="text-xs text-muted" style={{ marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Line Loading</h4>
                <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent-green)' }}></span> Normal (&lt;60%)</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent-amber)' }}></span> Warning (60-85%)</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent-red)' }}></span> Overloaded (&gt;85%)</div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-lg">
          <CongestionPanel gridState={gridState} />
        </div>
      </div>
    </div>
  );
}
