import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// IEEE 13-bus feeder buses that can host a household
const AVAILABLE_BUSES = [
  { id: 2,  label: 'Bus 632' },
  { id: 3,  label: 'Bus 633' },
  { id: 4,  label: 'Bus 634' },
  { id: 5,  label: 'Bus 645' },
  { id: 6,  label: 'Bus 646' },
  { id: 7,  label: 'Bus 671' },
  { id: 8,  label: 'Bus 692' },
  { id: 9,  label: 'Bus 675' },
  { id: 10, label: 'Bus 611' },
  { id: 11, label: 'Bus 652' },
  { id: 12, label: 'Bus 680' },
];

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('buyer');
  const [busId, setBusId] = useState(2);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const user = await signup(name, email, password, role, busId);
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
              Join the microgrid trading network
            </p>
            <div className="auth-brand-features">
              <div className="auth-feature">
                <span className="auth-feature-icon">🏠</span>
                <span>Represent a house on the grid</span>
              </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">💰</span>
                <span>Trade solar surplus for revenue</span>
              </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">🌱</span>
                <span>Support clean energy locally</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right side — form */}
        <div className="auth-form-section">
          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-form-header">
              <h2>Create Account</h2>
              <p className="text-muted">Register as a buyer or seller</p>
            </div>

            {error && (
              <div className="auth-error">
                <span>⚠</span>
                {error}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="signup-name" className="form-label">Full Name</label>
              <input
                id="signup-name"
                type="text"
                className="form-input"
                placeholder="John Doe"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                minLength={2}
              />
            </div>

            <div className="form-group">
              <label htmlFor="signup-email" className="form-label">Email</label>
              <input
                id="signup-email"
                type="email"
                className="form-input"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="signup-password" className="form-label">Password</label>
              <input
                id="signup-password"
                type="password"
                className="form-input"
                placeholder="Min 6 characters"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="signup-role" className="form-label">Role</label>
                <select
                  id="signup-role"
                  className="form-input"
                  value={role}
                  onChange={e => setRole(e.target.value)}
                >
                  <option value="buyer">Buyer</option>
                  <option value="seller">Seller</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="signup-bus" className="form-label">Grid Bus</label>
                <select
                  id="signup-bus"
                  className="form-input"
                  value={busId}
                  onChange={e => setBusId(Number(e.target.value))}
                >
                  {AVAILABLE_BUSES.map(bus => (
                    <option key={bus.id} value={bus.id}>{bus.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary auth-submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div>
                  Creating account...
                </>
              ) : (
                'Create Account'
              )}
            </button>

            <p className="auth-switch">
              Already have an account?{' '}
              <Link to="/login" className="auth-link">Sign in</Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
