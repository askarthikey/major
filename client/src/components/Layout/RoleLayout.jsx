import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import Header from './Header';
import { Button, Badge } from '../../components/ui';

export default function RoleLayout({ role }) {
  const { user, logout } = useAuth();
  const { isConnected } = useWebSocket();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navItems = {
    seller: [
      { to: '/seller', label: 'Energy overview', icon: '◈', end: true },
      { to: '/seller/history', label: 'Trade history', icon: '↗' },
    ],
    buyer: [
      { to: '/buyer', label: 'Energy marketplace', icon: '◈', end: true },
      { to: '/buyer/history', label: 'My bids & trades', icon: '↗' },
    ],
    admin: [
      { to: '/admin', label: 'Grid state', icon: '◈', end: true },
      { to: '/admin/trades', label: 'Trade registry', icon: '↗' },
      { to: '/admin/stats', label: 'Analytics', icon: '◌' },
      { to: '/admin/ledger', label: 'Ledger integrity', icon: '⌁' },
    ],
  };

  const items = navItems[role] || [];
  const roleTitle = role === 'admin' ? 'Operator workspace' : role === 'seller' ? 'Seller workspace' : 'Buyer workspace';

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div className="sidebar-logo">
          <h1><span className="brand-mark">✦</span> Solar P2P</h1>
          <p>Local energy, intelligently shared</p>
        </div>

        <nav className="sidebar-nav">
          <div className="sidebar-section-label">Workspace</div>
          {items.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="flex items-center gap-sm">
                <span className="text-sm nav-icon">{item.icon}</span>
                {item.label}
              </span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-network-card">
          <div className="network-card-icon">⌁</div>
          <div>
            <strong>Grid network</strong>
            <span>13 active buses</span>
          </div>
          <span className="network-live-dot" />
        </div>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">
              {user?.name?.charAt(0)?.toUpperCase() || '?'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.name}</span>
              <Badge variant={role}>{role}</Badge>
            </div>
          </div>
          <Button variant="ghost" className="btn-sm btn-logout" onClick={handleLogout}>Sign out</Button>
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
        <Header
          isConnected={isConnected}
          simulationTime={user?.bus_id != null ? `Bus ${user.bus_id}` : null}
          isRunning={true}
          roleTitle={roleTitle}
          currentPath={location.pathname}
        />

        <div className="app-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
