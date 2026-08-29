import { StatCard } from '../dashboard/StatCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { NetworkIcon, MapPinIcon, OptimizeIcon, ClockIcon } from '../common/Icons.jsx'

export function NetworkStatsCards({ networkData }) {
  const nNodes = networkData?.n_nodes ?? 0
  const nEdges = networkData?.n_edges ?? 0
  const nDepots = networkData?.n_depots ?? 0
  const nCustomers = networkData?.n_customers ?? 0
  const nIntersections = networkData?.n_intersections ?? 0
  const avgDegree = nNodes > 0 ? (nEdges / nNodes).toFixed(1) : '0.0'
  const seed = networkData?.seed ?? 42
  const gridSize = networkData?.grid_size_km ?? 10.0
  const connectRadius = networkData?.connect_radius_km ?? 3.5

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6 w-full">
      {/* Stat 1: Total Nodes */}
      <StatCard
        title="Total Nodes"
        value={nNodes > 0 ? `${nNodes} Nodes` : 'No Nodes'}
        subtitle={
          nNodes > 0
            ? `${nDepots} Depot · ${nCustomers} Cust · ${nIntersections} Inter`
            : 'Awaiting graph generation'
        }
        accentColor="blue"
        icon={<NetworkIcon className="w-4 h-4" />}
      />

      {/* Stat 2: Road Segments */}
      <StatCard
        title="Road Segments"
        value={nEdges > 0 ? `${nEdges} Edges` : '0 Edges'}
        subtitle={
          nEdges > 0
            ? 'Directed road graph connectivity'
            : 'No road segments formed'
        }
        accentColor="green"
        icon={<MapPinIcon className="w-4 h-4" />}
      />

      {/* Stat 3: Graph Density */}
      <StatCard
        title="Graph Connectivity"
        value={nNodes > 0 ? `${avgDegree} Edges/Node` : '0.0'}
        subtitle={
          nNodes > 0
            ? `Radius ${connectRadius}km · Grid ${gridSize}km`
            : 'Topological connectivity score'
        }
        accentColor="purple"
        icon={<OptimizeIcon className="w-4 h-4" />}
      />

      {/* Stat 4: Network Status */}
      <StatCard
        title="Network Status"
        value={nNodes > 0 ? 'Network Ready' : 'Uninitialized'}
        valueColor={nNodes > 0 ? 'text-emerald-400' : 'text-slate-500'}
        subtitle={
          nNodes > 0
            ? `Seed: ${seed} · Ready for fleet configuration`
            : 'Execute generation to begin'
        }
        badge={
          nNodes > 0 ? (
            <Badge variant="success" size="sm" dot>
              Operational
            </Badge>
          ) : (
            <Badge variant="neutral" size="sm">
              Idle
            </Badge>
          )
        }
        accentColor="amber"
        icon={<ClockIcon className="w-4 h-4" />}
      />
    </div>
  )
}

export default NetworkStatsCards
