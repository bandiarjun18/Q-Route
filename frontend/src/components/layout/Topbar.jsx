import { useLocation } from 'react-router-dom'
import { Badge } from '../ui/Badge.jsx'
import { Button } from '../ui/Button.jsx'

export function Topbar() {
  const location = useLocation()

  const getPageTitle = (pathname) => {
    switch (pathname) {
      case '/':
      case '/dashboard':
        return 'Dashboard'
      case '/network':
        return 'Network'
      case '/fleet':
        return 'Fleet'
      case '/optimization':
        return 'Optimization'
      case '/routes':
        return 'Live Routes'
      case '/incidents':
        return 'Incidents'
      case '/analytics':
        return 'Analytics'
      default:
        return 'Dashboard'
    }
  }

  const pageTitle = getPageTitle(location.pathname)

  return (
    <header className="h-14 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-5 sm:px-6 flex items-center justify-between gap-4 sticky top-0 z-40 w-full select-none">
      {/* Breadcrumb Path */}
      <div className="flex items-center gap-2 text-xs sm:text-sm">
        <span className="text-slate-500 font-medium hidden sm:inline">Q-Route</span>
        <span className="text-slate-700 hidden sm:inline">/</span>
        <span className="text-slate-200 font-semibold">{pageTitle}</span>
      </div>

      {/* Right Controls: Visual placeholders */}
      <div className="flex items-center gap-2.5">
        {/* API status placeholder */}
        <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-900/90 border border-slate-800 rounded-lg px-2.5 py-1">
          <Badge variant="success" size="sm" dot>
            API Online
          </Badge>
        </div>

        {/* Reset button placeholder */}
        <Button
          variant="ghost"
          size="sm"
          className="text-xs h-7.5 px-2.5 text-slate-400 hover:text-slate-200 border border-slate-800/80 bg-slate-900/50"
        >
          <span>↺</span>
          <span className="hidden sm:inline ml-1">Reset</span>
        </Button>

        {/* Documentation button placeholder */}
        <Button
          variant="ghost"
          size="sm"
          className="text-xs h-7.5 px-2.5 text-slate-400 hover:text-slate-200 border border-slate-800/80 bg-slate-900/50 hidden md:flex items-center gap-1"
        >
          <span>Docs</span>
          <span className="text-slate-500 text-[10px]">↗</span>
        </Button>

        {/* User/profile avatar placeholder */}
        <div className="w-7 h-7 rounded-full bg-blue-600/20 border border-blue-500/40 text-blue-400 flex items-center justify-center text-xs font-bold">
          QR
        </div>
      </div>
    </header>
  )
}

export default Topbar
