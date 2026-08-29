import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Badge } from '../ui/Badge.jsx'
import {
  NetworkIcon,
  FleetIcon,
  OptimizeIcon,
  IncidentsIcon,
  ClockIcon,
} from '../common/Icons.jsx'

export function RecentActivity({ events = [], className = '' }) {
  const getEventIcon = (type) => {
    switch (type) {
      case 'incident':
        return <IncidentsIcon className="w-4 h-4" />
      case 'optimize':
        return <OptimizeIcon className="w-4 h-4" />
      case 'fleet':
        return <FleetIcon className="w-4 h-4" />
      case 'network':
      default:
        return <NetworkIcon className="w-4 h-4" />
    }
  }

  const getIconContainerStyle = (type) => {
    switch (type) {
      case 'incident':
        return 'bg-rose-950/80 border border-rose-800/60 text-rose-400'
      case 'optimize':
        return 'bg-amber-950/80 border border-amber-800/60 text-amber-400'
      case 'fleet':
        return 'bg-blue-950/80 border border-blue-800/60 text-blue-400'
      case 'network':
      default:
        return 'bg-emerald-950/80 border border-emerald-800/60 text-emerald-400'
    }
  }

  return (
    <Card className={`w-full ${className}`}>
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>
            Latest network, fleet, optimization, and incident events
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium hidden sm:inline">
            {events.length} Events
          </span>
          <button
            type="button"
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors cursor-pointer px-2.5 py-1 rounded-lg hover:bg-slate-800/60 border border-transparent hover:border-slate-700"
          >
            View All
          </button>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-0">
        {events.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {events.map((event) => (
              <div
                key={event.id}
                className="px-5 py-4 flex items-center justify-between gap-4 hover:bg-slate-800/30 transition-colors"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${getIconContainerStyle(
                      event.type
                    )}`}
                  >
                    {getEventIcon(event.type)}
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-sm font-semibold text-slate-200 truncate">{event.title}</h4>
                    <p className="text-xs text-slate-400 truncate mt-0.5">{event.description}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-slate-500 hidden sm:inline font-mono">
                    {event.timeAgo}
                  </span>
                  <Badge
                    variant={
                      event.status === 'success'
                        ? 'success'
                        : event.status === 'warning'
                        ? 'warning'
                        : 'neutral'
                    }
                    size="sm"
                  >
                    {event.badge || 'Logged'}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 px-6 text-center text-xs sm:text-sm text-slate-500 space-y-2 min-h-[140px] flex flex-col items-center justify-center">
            <div className="w-8 h-8 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-500 mb-1">
              <ClockIcon className="w-4 h-4" />
            </div>
            <p className="font-medium text-slate-400 text-sm">No activity recorded in the current session.</p>
            <p className="text-slate-500 text-xs max-w-md mx-auto leading-relaxed">
              Operations such as network generation, fleet configuration, route optimization, and incident management will appear here.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default RecentActivity
