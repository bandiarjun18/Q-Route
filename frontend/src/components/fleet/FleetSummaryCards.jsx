import { StatCard } from '../dashboard/StatCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { FleetIcon, PackageIcon, UsersIcon, CheckCircleIcon, ClockIcon } from '../common/Icons.jsx'

export function FleetSummaryCards({ vehicles = [], customers = [] }) {
  const nVehicles = vehicles.length
  const nCustomers = customers.length
  const totalCapacity = vehicles.reduce((sum, v) => sum + Number(v.capacity || 0), 0)
  const totalDemand = customers.reduce((sum, c) => sum + Number(c.demand || 0), 0)
  const avgCapacity = nVehicles > 0 ? (totalCapacity / nVehicles).toFixed(1) : '0.0'

  const isReady = nVehicles >= 1 && nCustomers >= 1 && totalCapacity >= totalDemand
  const isOverCapacity = totalDemand > totalCapacity && totalCapacity > 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6 w-full">
      {/* 1. Vehicles */}
      <StatCard
        title="Vehicles"
        value={nVehicles > 0 ? `${nVehicles} Units` : '0 Units'}
        subtitle={
          nVehicles > 0
            ? `${nVehicles} vehicles active in dispatch fleet`
            : 'No fleet units configured'
        }
        accentColor="blue"
        icon={<FleetIcon className="w-4 h-4" />}
      />

      {/* 2. Total Fleet Capacity */}
      <StatCard
        title="Total Fleet Capacity"
        value={totalCapacity > 0 ? `${totalCapacity.toFixed(0)} units` : '0 units'}
        subtitle={
          nVehicles > 0
            ? `Average ${avgCapacity} units payload / vehicle`
            : 'Zero total payload volume'
        }
        accentColor="green"
        icon={<PackageIcon className="w-4 h-4" />}
      />

      {/* 3. Customer Orders */}
      <StatCard
        title="Customer Orders"
        value={nCustomers > 0 ? `${nCustomers} Orders` : '0 Orders'}
        subtitle={
          nCustomers > 0
            ? `Total cargo demand: ${totalDemand.toFixed(1)} units`
            : 'No delivery demand configured'
        }
        accentColor="purple"
        icon={<UsersIcon className="w-4 h-4" />}
      />

      {/* 4. Fleet Readiness */}
      <StatCard
        title="Fleet Readiness"
        value={
          isReady
            ? 'Ready to Solve'
            : isOverCapacity
            ? 'Capacity Deficit'
            : 'Config Required'
        }
        valueColor={
          isReady
            ? 'text-emerald-400'
            : isOverCapacity
            ? 'text-rose-400'
            : 'text-amber-400'
        }
        subtitle={
          isReady
            ? `${nVehicles} vehicles ready to serve ${nCustomers} orders`
            : isOverCapacity
            ? `Demand (${totalDemand.toFixed(1)}) exceeds capacity (${totalCapacity.toFixed(1)})`
            : 'Add ≥1 vehicle and ≥1 customer order'
        }
        badge={
          isReady ? (
            <Badge variant="success" size="sm" dot>
              Ready
            </Badge>
          ) : isOverCapacity ? (
            <Badge variant="danger" size="sm" dot>
              Overload
            </Badge>
          ) : (
            <Badge variant="warning" size="sm" dot>
              Incomplete
            </Badge>
          )
        }
        accentColor={isReady ? 'green' : isOverCapacity ? 'rose' : 'amber'}
        icon={isReady ? <CheckCircleIcon className="w-4 h-4" /> : <ClockIcon className="w-4 h-4" />}
      />
    </div>
  )
}

export default FleetSummaryCards
