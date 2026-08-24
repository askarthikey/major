export default function Header({ isConnected, simulationTime, isRunning }) {
  return (
    <header className="app-header">
      <div className="flex items-center gap-md">
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
          P2P Trading Dashboard
        </h2>
        {simulationTime && (
          <span className="badge pending" style={{ fontSize: '0.8rem' }}>
            🕐 {simulationTime}
          </span>
        )}
      </div>

      <div className="flex items-center gap-md">
        {isRunning && (
          <span className="badge executed">
            <div className="pulse-dot" style={{ width: 6, height: 6 }}></div>
            LIVE
          </span>
        )}
        <span className={`badge ${isConnected ? 'online' : 'offline'}`}>
          {isConnected ? '● Connected' : '○ Disconnected'}
        </span>
      </div>
    </header>
  );
}
