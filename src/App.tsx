import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ClientsPage } from './pages/ClientsPage';
import { JobsPage } from './pages/JobsPage';
import { RestorePage } from './pages/RestorePage';
import { StoragePage } from './pages/StoragePage';
import { PoliciesPage } from './pages/PoliciesPage';
import { ActivityPage } from './pages/ActivityPage';
import { SettingsPage } from './pages/SettingsPage';
import { SecurityPage } from './pages/SecurityPage';
import { AlertsPage } from './pages/AlertsPage';
import { OperationsPage } from './pages/OperationsPage';
import { CapacityPage } from './pages/CapacityPage';
import { ObservabilityPage } from './pages/ObservabilityPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { ReportsPage } from './pages/ReportsPage';
import { WorkloadsPage } from './pages/WorkloadsPage';
import { RecoveryVerificationPage } from './pages/RecoveryVerificationPage';
import { RecoveryReadinessPage } from './pages/RecoveryReadinessPage';
import { PolicyOrchestrationPage } from './pages/PolicyOrchestrationPage';
import { DisasterRecoveryPage } from './pages/DisasterRecoveryPage';
import { ReplicationPage } from './pages/ReplicationPage';

export const App: React.FC = () => {
  return (
    <AppProvider>
      <HashRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="clients/:id" element={<ClientsPage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="restore" element={<RestorePage />} />
            <Route path="storage" element={<StoragePage />} />
            <Route path="replication" element={<ReplicationPage />} />
            <Route path="dr" element={<DisasterRecoveryPage />} />
            <Route path="recovery-verification" element={<RecoveryVerificationPage />} />
            <Route path="recovery-readiness" element={<RecoveryReadinessPage />} />
            <Route path="workloads" element={<WorkloadsPage />} />
            <Route path="policy-orchestration" element={<PolicyOrchestrationPage />} />
            <Route path="operations" element={<OperationsPage />} />
            <Route path="operations/incidents" element={<IncidentsPage />} />
            <Route path="capacity" element={<CapacityPage />} />
            <Route path="observability" element={<ObservabilityPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="policies" element={<PoliciesPage />} />
            <Route path="security" element={<SecurityPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </AppProvider>
  );
};

export default App;
