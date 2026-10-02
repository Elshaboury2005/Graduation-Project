import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useLocation, useNavigate } from 'react-router-dom';
import { setApiToken } from '../../api/client';

export default function TopBar() {
  const { logout, username } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    setApiToken(null); // Clear Axios interceptor token
    logout();          // Clear React context
    navigate('/login');
  };

  const getPageTitle = () => {
    switch (true) {
      case location.pathname === '/': return 'Dashboard';
      case location.pathname.startsWith('/pipelines'): return 'Pipeline Management';
      case location.pathname.startsWith('/reliability'): return 'Reliability Testing';
      case location.pathname.startsWith('/reports'): return 'Reports';
      default: return 'Platform';
    }
  };

  return (
    <header className="h-16 bg-slate-800 border-b border-slate-700 flex items-center justify-between px-6">
      <h2 className="text-lg font-semibold text-slate-100">{getPageTitle()}</h2>
      <div className="flex items-center space-x-4">
        <span className="text-sm text-slate-400">User: {username}</span>
        <button
          onClick={handleLogout}
          className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
