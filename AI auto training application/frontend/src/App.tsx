import { Route, Routes } from 'react-router-dom';
import { AppShell } from './layout/AppShell';
import { RequireAuth } from './layout/RequireAuth';
import { LoginPage } from './features/auth/LoginPage';
import { DashboardPage } from './features/projects/DashboardPage';
import { NewProjectPage } from './features/projects/NewProjectPage';
import { ProjectDetailPage } from './features/projects/ProjectDetailPage';
import { DatasetUploadPage } from './features/datasets/DatasetUploadPage';
import { CvatComingSoonPage } from './features/cvat/CvatComingSoonPage';
import { AnalysisPage } from './features/analysis/AnalysisPage';
import { TrainingStartPage } from './features/training/TrainingStartPage';
import { TrainingMonitorPage } from './features/training/TrainingMonitorPage';
import { SettingsPage } from './features/settings/SettingsPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="projects/new" element={<NewProjectPage />} />
          <Route path="projects/:id" element={<ProjectDetailPage />} />
          <Route path="projects/:id/dataset" element={<DatasetUploadPage />} />
          <Route path="projects/:id/cvat" element={<CvatComingSoonPage />} />
          <Route path="projects/:id/analyze/:versionId" element={<AnalysisPage />} />
          <Route path="projects/:id/train" element={<TrainingStartPage />} />
          <Route path="projects/:id/train/:jobId" element={<TrainingMonitorPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}

function NotFound() {
  return (
    <div className="py-12 text-center text-sm text-slate-500">
      Page not found.
    </div>
  );
}
