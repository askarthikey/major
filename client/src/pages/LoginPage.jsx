import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button, Input } from '../components/ui';

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
            <div className="auth-brand-icon">✦</div>
            <h1 className="auth-brand-title">Solar P2P</h1>
            <p className="auth-brand-subtitle">
              A calmer, smarter way to share<br />the energy your neighborhood makes.
            </p>
            <div className="auth-brand-features">
              <div className="auth-feature">
                <span className="auth-feature-icon">01</span>
                <span>Trade with the pulse of your grid</span>
                </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">02</span>
                <span>AI safety behind every decision</span>
                </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">03</span>
                <span>A transparent record you can trust</span>
                </div>
            </div>
          </div>
        </div>

        {/* Right side — form */}
        <div className="auth-form-section">
          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-form-header">
              <div className="text-xs text-muted uppercase tracking-widest mb-sm">Member access</div>
              <h2>Welcome back</h2>
              <p className="text-muted text-sm">Continue to your energy network.</p>
            </div>

            {error && (
              <div className="auth-error">
                <span>⚠</span>
                {error}
                </div>
            )}

            <Input
              label="Email"
              id="login-email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />

            <Input
              label="Password"
              id="login-password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />

            <Button
              type="submit"
              variant="primary"
              className="auth-submit"
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
            </Button>

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
