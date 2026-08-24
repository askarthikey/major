export default function Sidebar() {
  return (
    <aside className="app-sidebar">
      <div className="sidebar-logo">
        <h1>☀️ Solar P2P</h1>
        <p>Microgrid Trading System</p>
      </div>

      <nav className="sidebar-nav">
        <a className="nav-item active" href="#dashboard">
          <span>📊</span> Dashboard
        </a>
        <a className="nav-item" href="#grid">
          <span>⚡</span> Grid Network
        </a>
        <a className="nav-item" href="#trades">
          <span>🔄</span> Trade History
        </a>
        <a className="nav-item" href="#analytics">
          <span>📈</span> Analytics
        </a>
        <a className="nav-item" href="#settings">
          <span>⚙️</span> Settings
        </a>
      </nav>

      <div className="sidebar-footer">
        <div className="flex items-center gap-sm">
          <div className="pulse-dot"></div>
          <span className="text-xs text-muted">System Online</span>
        </div>
        <p className="text-xs text-muted mt-sm">GNN Feasibility Gate v1.0</p>
      </div>
    </aside>
  );
}
