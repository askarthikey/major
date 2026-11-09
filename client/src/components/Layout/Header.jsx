import { useState } from 'react';
import { Badge } from '../../components/ui';

export default function Header({ isConnected, simulationTime, isRunning, roleTitle }) {
  const [showAlerts, setShowAlerts] = useState(false);

  return (
    <header className="app-header">
      <div className="flex items-center gap-md">
        <div>
          <div className="text-xs text-muted uppercase tracking-widest">{roleTitle || 'Solar P2P'} / live network</div>
          <h2 className="text-sm" style={{ color: 'var(--text-primary)' }}>Grid intelligence, in motion</h2>
        </div>
        {simulationTime && (
          <Badge variant="pending" className="text-xs">
            {simulationTime}
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-md">
        <div className="header-actions">
          <button className="icon-button" aria-label="View notifications" onClick={() => setShowAlerts(!showAlerts)}>
            ◌<span className="notification-dot" />
          </button>
          {showAlerts && (
            <div className="notification-popover">
              <div className="eyebrow">Notifications</div>
              <strong>Everything is operating normally.</strong>
              <span>No new grid events.</span>
            </div>
          )}
        </div>
        {isRunning && (
          <Badge variant="executed" className="flex items-center gap-xs">
            <div className="pulse-dot"></div>
            LIVE FEED
          </Badge>
        )}
        <Badge variant={isConnected ? 'online' : 'offline'}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </Badge>
      </div>
    </header>
  );
}
