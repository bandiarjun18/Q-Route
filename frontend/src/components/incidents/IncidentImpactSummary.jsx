import { StatCard } from '../dashboard/StatCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { FleetIcon, RoutesIcon, CheckCircleIcon, IncidentsIcon } from '../common/Icons.jsx'

export function IncidentImpactSummary({ incidentResult }) {
  const hasResult = incidentResult != null
  const nAffected = hasResult ? incidentResult.n_affected : 0
  const updatedRoutesCount = hasResult ? incidentResult.updated_routes?.length || 0 : 0
  const unaffectedCount = hasResult ? incidentResult.unaffected_route_count : 0
  const isClosure = hasResult ? Boolean(incidentResult.is_closure) : false
  const severity = hasResult ? incidentResult.severity : 'NONE'

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6 w-full">
      {/* 1. Affected Vehicles */}
      <StatCard
        title="Affected Vehicles"
        value={hasResult ? `${nAffected} Units` : '0 Units'}
        valueColor={nAffected > 0 ? 'text-amber-400' : 'text-slate-400'}
        subtitle={
          hasResult
            ? `${nAffected} vehicles traversed incident corridor`
            : 'No vehicle conflicts registered'
        }
        accentColor="amber"
        icon={<FleetIcon className="w-4 h-4" />}
      />

      {/* 2. Updated Routes */}
      <StatCard
        title="Updated Routes"
        value={hasResult ? `${updatedRoutesCount} Routes` : '0 Routes'}
        valueColor={updatedRoutesCount > 0 ? 'text-blue-400' : 'text-slate-400'}
        subtitle={
          hasResult
            ? 'Dynamically re-optimized path schedules'
            : 'No route recalculations required'
        }
        accentColor="blue"
        icon={<RoutesIcon className="w-4 h-4" />}
      />

      {/* 3. Unaffected Routes */}
      <StatCard
        title="Unaffected Routes"
        value={hasResult ? `${unaffectedCount} Routes` : '0 Routes'}
        valueColor={unaffectedCount > 0 ? 'text-emerald-400' : 'text-slate-400'}
        subtitle={
          hasResult
            ? 'Preserved original optimal itineraries'
            : 'No routes unaffected'
        }
        accentColor="green"
        icon={<CheckCircleIcon className="w-4 h-4" />}
      />

      {/* 4. Disruption Status & Severity */}
      <StatCard
        title="Disruption Status"
        value={
          hasResult
            ? isClosure
              ? 'ROAD CLOSED'
              : `${severity} IMPACT`
            : 'Nominal'
        }
        valueColor={
          hasResult
            ? isClosure
              ? 'text-rose-400'
              : 'text-amber-400'
            : 'text-emerald-400'
        }
        subtitle={
          hasResult
            ? `Corridor N${incidentResult.edge_u} → N${incidentResult.edge_v}`
            : 'Full network traffic clear'
        }
        badge={
          hasResult ? (
            isClosure ? (
              <Badge variant="danger" size="sm" dot>
                Closed
              </Badge>
            ) : (
              <Badge variant="warning" size="sm" dot>
                {severity}
              </Badge>
            )
          ) : (
            <Badge variant="success" size="sm" dot>
              Clear
            </Badge>
          )
        }
        accentColor={hasResult ? (isClosure ? 'rose' : 'amber') : 'green'}
        icon={<IncidentsIcon className="w-4 h-4" />}
      />
    </div>
  )
}

export default IncidentImpactSummary
