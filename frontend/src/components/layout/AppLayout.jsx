import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar.jsx'
import { Topbar } from './Topbar.jsx'

export function AppLayout() {
  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-950 text-slate-100 font-sans antialiased selection:bg-blue-600 selection:text-white">
      {/* Persistent Left Sidebar: 240px */}
      <Sidebar />

      {/* Main Content Column */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen bg-slate-950">
        {/* Top Navigation */}
        <Topbar />

        {/* Dynamic Page Container */}
        <main className="flex-1 min-w-0 w-full p-6 sm:p-8 lg:p-8 space-y-6 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
