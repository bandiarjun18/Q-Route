import { StatCard } from '../dashboard/StatCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { FleetIcon, RoutesIcon, MapPinIcon, ClockIcon } from '../common/Icons.jsx'

export function RouteSummaryCards({ routesData }) {
  const routes = routesData?.routes || []
  const totalActive = routesData?.total_active ?? routes.length
  const totalDist = routes.reduce((sum, r) => sum + Number(r.total_distance || 0), 0)
  const totalTime = routes.reduce((sum, r) => sum + Number(r.total_travel_time || 0), 0)
  const avgDist = routes.length > 0 ? (totalDist / routes.length).toFixed(1) : '0.0'

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6 w-full">
      {/* 1. Active Vehicles */}
      <StatCard
        title="Active Vehicles"
        value={routes.length > 0 ? `${routes.length} Units` : '0 Units'}
        subtitle={
          routes.length > 0
            ? `${routes.length} vehicles currently deployed on routes`
            : 'No vehicles on active routes'
        }
        accentColor="blue"
        icon={<FleetIcon className="w-4 h-4" />}
      />

      {/* 2. Total Active Routes */}
      <StatCard
        title="Total Active Routes"
        value={totalActive > 0 ? `${totalActive} Routes` : '0 Routes'}
        valueColor={totalActive > 0 ? 'text-emerald-400' : 'text-slate-500'}
        subtitle={
          totalActive > 0
            ? 'Optimized multi-vehicle paths active'
            : 'Awaiting route optimization'
        }
        badge={
          totalActive > 0 ? (
            <Badge variant="success" size="sm" dot>
              Active
            </Badge>
          ) : (
            <Badge variant="neutral" size="sm">
              Idle
            </Badge>
          )
        }
        accentColor="green"
        icon={<RoutesIcon className="w-4 h-4" />}
      />

      {/* 3. Total Distance */}
      <StatCard
        title="Total Distance"
        value={totalDist > 0 ? `${totalDist.toFixed(1)} km` : '0.0 km'}
        subtitle={
          routes.length > 0
            ? `Average ${avgDist} km per vehicle route`
            : 'Zero total transit distance'
        }
        accentColor="purple"
        icon={<MapPinIcon className="w-4 h-4" />}
      />

      {/* 4. Total Travel Time */}
      <StatCard
        title="Total Travel Time"
        value={totalTime > 0 ? `${totalTime.toFixed(1)} min` : '0.0 min'}
        subtitle={
          routes.length > 0
            ? 'Effective cumulative fleet travel duration'
            : 'Zero active transit time'
        }
        accentColor="amber"
        icon={<ClockIcon className="w-4 h-4" />}
      />
    </div>
  )
}

export default RouteSummaryCards
