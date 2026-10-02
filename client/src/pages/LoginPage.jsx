import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const user = await login(email, password);
      navigate(`/${user.role}`, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        {/* Left side — branding */}
        <div className="auth-brand">
          <div className="auth-brand-content">
            <div className="auth-brand-icon">☀️</div>
            <h1 className="auth-brand-title">Solar P2P</h1>
            <p className="auth-brand-subtitle">
              GNN-Constrained Peer-to-Peer<br />Microgrid Trading System
            </p>
            <div className="auth-brand-features">
              <div className="auth-feature">
                <span className="auth-feature-icon">⚡</span>
                <span>Real-time grid-aware trading</span>
              </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">🧠</span>
                <span>AI-powered feasibility checks</span>
              </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">🔒</span>
                <span>Tamper-evident trade ledger</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right side — form */}
        <div className="auth-form-section">
          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-form-header">
              <h2>Welcome back</h2>
              <p className="text-muted">Sign in to your trading account</p>
            </div>

            {error && (
              <div className="auth-error">
                <span>⚠</span>
                {error}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="login-email" className="form-label">Email</label>
              <input
                id="login-email"
                type="email"
                className="form-input"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="form-group">
              <label htmlFor="login-password" className="form-label">Password</label>
              <input
                id="login-password"
                type="password"
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary auth-submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div>
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>

            <p className="auth-switch">
              Don't have an account?{' '}
              <Link to="/signup" className="auth-link">Create one</Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
