import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout.jsx'
import { Dashboard } from './pages/Dashboard.jsx'
import { Network } from './pages/Network.jsx'
import { Fleet } from './pages/Fleet.jsx'
import { Optimization } from './pages/Optimization.jsx'
import { LiveRoutes } from './pages/LiveRoutes.jsx'
import { Incidents } from './pages/Incidents.jsx'
import { Analytics } from './pages/Analytics.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="network" element={<Network />} />
          <Route path="fleet" element={<Fleet />} />
          <Route path="optimization" element={<Optimization />} />
          <Route path="routes" element={<LiveRoutes />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
