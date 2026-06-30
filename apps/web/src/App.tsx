import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DownloadsPage } from './pages/DownloadsPage'
import { PreviewPage } from './pages/PreviewPage'
import { ProgressPage } from './pages/ProgressPage'
import { ProjectListPage } from './pages/ProjectListPage'
import { ProofreadPage } from './pages/ProofreadPage'
import { SkillsPage } from './pages/SkillsPage'
import { UploadConfigPage } from './pages/UploadConfigPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <ProjectListPage /> },
      { path: 'upload', element: <UploadConfigPage /> },
      { path: 'projects/:projectId/progress', element: <ProgressPage /> },
      { path: 'projects/:projectId/proofread', element: <ProofreadPage /> },
      { path: 'projects/:projectId/preview', element: <PreviewPage /> },
      { path: 'projects/:projectId/downloads', element: <DownloadsPage /> },
      { path: 'skills', element: <SkillsPage /> },
    ],
  },
])
