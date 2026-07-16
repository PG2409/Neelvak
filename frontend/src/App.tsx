
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ChatCanvas from './components/ChatCanvas'
import ProjectsDashboard from './components/ProjectsDashboard'
import ProjectWorkspace from './components/ProjectWorkspace'
import SettingsDashboard from './components/SettingsDashboard'

const PlaceholderPage = ({ title }: { title: string }) => (
  <div className="flex-1 flex items-center justify-center text-text-muted">
    {title} - (Working Route)
  </div>
)

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/chats" replace />} />
          <Route path="chats" element={<ChatCanvas />} />
          <Route path="projects" element={<ProjectsDashboard />} />
          <Route path="projects/:id" element={<ProjectWorkspace />} />
          
          <Route path="artifacts" element={<PlaceholderPage title="Artifacts" />} />
          <Route path="code" element={<PlaceholderPage title="Code Workspace" />} />
          <Route path="customize" element={<SettingsDashboard />} />
          <Route path="*" element={<PlaceholderPage title="404 Not Found" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
