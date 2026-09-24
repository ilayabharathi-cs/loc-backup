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
import { ReplicationPage } from './pages/ReplicationPage';
import { TopologyPage } from './pages/TopologyPage';
import { SecurityPage } from './pages/SecurityPage';
import { AlertsPage } from './pages/AlertsPage';
import { ClusterPage } from './pages/ClusterPage';
import { SchedulerPage } from './pages/SchedulerPage';
import { OperationsPage } from './pages/OperationsPage';
import { CapacityPage } from './pages/CapacityPage';
import { ObservabilityPage } from './pages/ObservabilityPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { ReportsPage } from './pages/ReportsPage';
import { WorkloadsPage } from './pages/WorkloadsPage';
import { RecoveryVerificationPage } from './pages/RecoveryVerificationPage';
import { RecoveryReadinessPage } from './pages/RecoveryReadinessPage';
import { PolicyOrchestrationPage } from './pages/PolicyOrchestrationPage';
import { ApplicationRestorePage } from './pages/ApplicationRestorePage';
import { StorageTiersPage } from './pages/StorageTiersPage';
import { CloudCredentialsPage } from './pages/CloudCredentialsPage';
import { DRRunbooksPage } from './pages/DRRunbooksPage';
import { DRRunbookDetailsPage } from './pages/DRRunbookDetailsPage';
import { DRExecutionPage } from './pages/DRExecutionPage';
import { InstantRecoveryPage } from './pages/InstantRecoveryPage';

export const App: React.FC = () => {
  return (
    <AppProvider>
      <HashRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="workloads" element={<WorkloadsPage />} />
            <Route path="recovery-verification" element={<RecoveryVerificationPage />} />
            <Route path="recovery-readiness" element={<RecoveryReadinessPage />} />
            <Route path="policy-orchestration" element={<PolicyOrchestrationPage />} />
            <Route path="application-restore" element={<ApplicationRestorePage />} />
            <Route path="operations" element={<OperationsPage />} />
            <Route path="operations/incidents" element={<IncidentsPage />} />
            <Route path="capacity" element={<CapacityPage />} />
            <Route path="observability" element={<ObservabilityPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="clients/:id" element={<ClientsPage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="restore" element={<RestorePage />} />
            <Route path="storage" element={<StoragePage />} />
            <Route path="storage/tiers" element={<StorageTiersPage />} />
            <Route path="storage/credentials" element={<CloudCredentialsPage />} />
            <Route path="storage/topology" element={<TopologyPage />} />
            <Route path="dr/runbooks" element={<DRRunbooksPage />} />
            <Route path="dr/runbooks/:id" element={<DRRunbookDetailsPage />} />
            <Route path="dr/executions/:id" element={<DRExecutionPage />} />
            <Route path="recovery/instant-mounts" element={<InstantRecoveryPage />} />
            <Route path="replication" element={<ReplicationPage />} />
            <Route path="security" element={<SecurityPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="cluster" element={<ClusterPage />} />
            <Route path="scheduler" element={<SchedulerPage />} />
            <Route path="policies" element={<PoliciesPage />} />
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
