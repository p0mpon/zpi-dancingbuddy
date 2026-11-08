// ProtectedRoute.jsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginRequiredRoute() {
    const { user, loading } = useAuth();

    if (loading) return <div>Loading...</div>;

    return user?.email ? <Outlet /> : <Navigate to="/login" replace />;
}