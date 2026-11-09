import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button, Input } from '../components/ui';

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
            <div className="auth-brand-icon">✦</div>
            <h1 className="auth-brand-title">Solar P2P</h1>
            <p className="auth-brand-subtitle">
              Make your energy count<br />for more than just your own home.
            </p>
            <div className="auth-brand-features">
              <div className="auth-feature">
                <span className="auth-feature-icon">01</span>
                <span>Bring your place into the network</span>
                </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">02</span>
                <span>Turn surplus into shared value</span>
                </div>
              <div className="auth-feature">
                <span className="auth-feature-icon">03</span>
                <span>Keep every exchange grid-safe</span>
                </div>
            </div>
          </div>
        </div>

        {/* Right side — form */}
        <div className="auth-form-section">
          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-form-header">
              <div className="text-xs text-muted uppercase tracking-widest mb-sm">Join the network</div>
              <h2>Create your account</h2>
              <p className="text-muted text-sm">Choose how you want to participate.</p>
            </div>

            {error && (
              <div className="auth-error">
                <span>⚠</span>
                {error}
                </div>
            )}

            <Input
              label="Full Name"
              id="signup-name"
              type="text"
              placeholder="John Doe"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              minLength={2}
            />

            <Input
              label="Email"
              id="signup-email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />

            <Input
              label="Password"
              id="signup-password"
              type="password"
              placeholder="Min 6 characters"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={6}
            />

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

            <Button
              type="submit"
              variant="primary"
              className="auth-submit"
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
            </Button>

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
