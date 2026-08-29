import { NavLink } from 'react-router-dom'
import {
  DashboardIcon,
  NetworkIcon,
  FleetIcon,
  OptimizeIcon,
  RoutesIcon,
  IncidentsIcon,
  AnalyticsIcon,
} from '../common/Icons.jsx'
import { Badge } from '../ui/Badge.jsx'

export function Sidebar() {
  const primaryNav = [
    { to: '/dashboard', label: 'Dashboard', icon: DashboardIcon },
  ]

  const workflowNav = [
    { to: '/network', label: 'Network', icon: NetworkIcon },
    { to: '/fleet', label: 'Fleet', icon: FleetIcon },
    { to: '/optimization', label: 'Optimization', icon: OptimizeIcon },
    { to: '/routes', label: 'Live Routes', icon: RoutesIcon },
    { to: '/incidents', label: 'Incidents', icon: IncidentsIcon },
    { to: '/analytics', label: 'Analytics', icon: AnalyticsIcon },
  ]

  return (
    <aside className="w-full md:w-[240px] shrink-0 bg-slate-950 border-r border-slate-800/90 flex flex-col md:min-h-screen select-none">
      {/* Brand Header */}
      <div className="h-16 px-5 border-b border-slate-800/80 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white text-sm shadow-xs shrink-0">
          Q
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-base text-slate-100 tracking-tight">Q-Route</span>
            <span className="text-[9px] font-mono text-blue-400 bg-blue-950/80 border border-blue-800/60 px-1 py-0.2 rounded font-semibold">
              v0.9
            </span>
          </div>
          <p className="text-xs text-slate-500 truncate font-medium">Intelligent Fleet Routing</p>
        </div>
      </div>

      {/* Navigation Section */}
      <nav className="p-3 flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-x-visible scrollbar-none flex-1">
        {/* Main View */}
        {primaryNav.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all shrink-0 md:shrink text-left cursor-pointer ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 font-semibold shadow-xs'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/80 border border-transparent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
                  <span className="flex-1 truncate">{item.label}</span>
                </>
              )}
            </NavLink>
          )
        })}

        <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-3 pt-4 pb-1 hidden md:block">
          Operations
        </div>

        {/* Workflow Views */}
        {workflowNav.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all shrink-0 md:shrink text-left cursor-pointer ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 font-semibold shadow-xs'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/80 border border-transparent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
                  <span className="flex-1 truncate">{item.label}</span>
                </>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* System Status Footer */}
      <div className="p-4 border-t border-slate-800/80 hidden md:block bg-slate-950">
        <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 space-y-2.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold text-slate-300">Pipeline Status</span>
            <Badge variant="neutral" size="sm">
              M10 Pass
            </Badge>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Network</span>
              <span className="font-mono text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                Ready
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Fleet</span>
              <span className="font-mono text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                Configured
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Solver</span>
              <span className="font-mono text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                Solved
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
