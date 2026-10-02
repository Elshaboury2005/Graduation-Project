import React from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';

// Layout
import PageLayout from './components/layout/PageLayout';

// Pages
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import PipelineManagement from './pages/PipelineManagement';
import PipelineDetails from './pages/PipelineDetails';
import ReliabilityTesting from './pages/ReliabilityTesting';
import Reports from './pages/Reports';

const AuthGuard = () => {
  const { token } = useAuth();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
};

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AuthGuard />}>
        <Route element={<PageLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pipelines" element={<PipelineManagement />} />
          <Route path="/pipelines/:runId" element={<PipelineDetails />} />
          <Route path="/reliability" element={<ReliabilityTesting />} />
          <Route path="/reports" element={<Reports />} />
        </Route>
      </Route>
    </Routes>
  );
}
