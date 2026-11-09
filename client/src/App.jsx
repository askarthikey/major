import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuth } from './contexts/AuthContext';

// Auth pages
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';

// Layout
import RoleLayout from './components/Layout/RoleLayout';
import ProtectedRoute from './components/Auth/ProtectedRoute';

// Seller pages
import SellerHome from './pages/seller/SellerHome';
import SellerHistory from './pages/seller/SellerHistory';

// Buyer pages
import BuyerHome from './pages/buyer/BuyerHome';
import BuyerHistory from './pages/buyer/BuyerHistory';

// Admin pages
import AdminGrid from './pages/admin/AdminGrid';
import AdminTrades from './pages/admin/AdminTrades';
import AdminStats from './pages/admin/AdminStats';
import AdminLedger from './pages/admin/AdminLedger';

import './App.css';

const queryClient = new QueryClient();

function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-overlay" style={{ minH: '100vh' }}>
        <div className="spinner"></div>
        <span>Loading Solar P2P...</span>
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        {/* Public routes */}
        <Route
          path="/login"
          element={user ? <Navigate to={`/${user.role}`} replace /> : <LoginPage />}
        />
        <Route
          path="/signup"
          element={user ? <Navigate to={`/${user.role}`} replace /> : <SignupPage />}
        />

        {/* Seller routes */}
        <Route
          path="/seller"
          element={
            <ProtectedRoute allowedRoles={['seller']}>
              <RoleLayout role="seller" />
            </ProtectedRoute>
          }
        >
          <Route index element={<SellerHome />} />
          <Route path="history" element={<SellerHistory />} />
        </Route>

        {/* Buyer routes */}
        <Route
          path="/buyer"
          element={
            <ProtectedRoute allowedRoles={['buyer']}>
              <RoleLayout role="buyer" />
            </ProtectedRoute>
          }
        >
          <Route index element={<BuyerHome />} />
          <Route path="history" element={<BuyerHistory />} />
        </Route>

        {/* Admin routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <RoleLayout role="admin" />
            </ProtectedRoute>
          }
        >
          <Route index element={<AdminGrid />} />
          <Route path="trades" element={<AdminTrades />} />
          <Route path="stats" element={<AdminStats />} />
          <Route path="ledger" element={<AdminLedger />} />
        </Route>

        {/* Default redirect */}
        <Route
          path="*"
          element={
            user ? (
              <Navigate to={`/${user.role}`} replace />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </QueryClientProvider>
  );
}

export default App;
