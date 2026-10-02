import { Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

/**
 * Route guard that checks authentication and role.
 *
 * - Unauthenticated → redirects to /login
 * - Wrong role → redirects to user's own home page
 * - Correct role → renders children
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <span>Authenticating...</span>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect to user's own role home
    return <Navigate to={`/${user.role}`} replace />;
  }

  return children;
}
