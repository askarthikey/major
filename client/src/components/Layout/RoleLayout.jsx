import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useWebSocket } from '../../hooks/useWebSocket';

export default function RoleLayout({ role }) {
  const { user, logout } = useAuth();
  const { isConnected } = useWebSocket();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navItems = {
    seller: [
      { to: '/seller', label: 'Grid Map', icon: '⚡', end: true },
      { to: '/seller/history', label: 'Trade History', icon: '📜' },
    ],
    buyer: [
      { to: '/buyer', label: 'Grid Map', icon: '⚡', end: true },
      { to: '/buyer/history', label: 'My Bids & Trades', icon: '📜' },
    ],
    admin: [
      { to: '/admin', label: 'Grid State', icon: '⚡', end: true },
      { to: '/admin/trades', label: 'All Trades', icon: '🔄' },
      { to: '/admin/stats', label: 'Analytics', icon: '📊' },
      { to: '/admin/ledger', label: 'Ledger Check', icon: '🔗' },
    ],
  };

  const items = navItems[role] || [];

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div className="sidebar-logo">
          <h1>☀️ Solar P2P</h1>
          <p>Microgrid Trading System</p>
        </div>

        <nav className="sidebar-nav">
          {items.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">
              {user?.name?.charAt(0)?.toUpperCase() || '?'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.name}</span>
              <span className={`badge ${role}`}>{role}</span>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm btn-logout" onClick={handleLogout}>
            Logout
          </button>
          <div className="flex items-center gap-sm mt-sm">
            <div className={`pulse-dot ${isConnected ? '' : 'offline'}`}></div>
            <span className="text-xs text-muted">
              {isConnected ? 'Live Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="app-main">
        <header className="app-header">
          <div className="flex items-center gap-md">
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
              {role === 'seller' && 'Seller Dashboard'}
              {role === 'buyer' && 'Buyer Dashboard'}
              {role === 'admin' && 'Admin Control Panel'}
            </h2>
            {user?.bus_id != null && (
              <span className="badge pending" style={{ fontSize: '0.75rem' }}>
                Bus {user.bus_id}
              </span>
            )}
          </div>
          <div className="flex items-center gap-md">
            <span className={`badge ${isConnected ? 'online' : 'offline'}`}>
              {isConnected ? '● Connected' : '○ Disconnected'}
            </span>
          </div>
        </header>

        <div className="app-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
