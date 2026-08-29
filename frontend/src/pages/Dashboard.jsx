import { PageHeader } from '../components/ui/PageHeader.jsx'
import { Badge } from '../components/ui/Badge.jsx'
import { StatCard } from '../components/dashboard/StatCard.jsx'
import { NetworkPreview } from '../components/dashboard/NetworkPreview.jsx'
import { ConvergencePreview } from '../components/dashboard/ConvergencePreview.jsx'
import { RecentActivity } from '../components/dashboard/RecentActivity.jsx'
import {
  FleetIcon,
  NetworkIcon,
  OptimizeIcon,
  MapPinIcon,
} from '../components/common/Icons.jsx'
import {
  dashboardStats,
  networkPreviewData,
  convergenceData,
  recentActivity,
} from '../data/dashboardData.js'

export function Dashboard() {
  const { activeVehicles, customersServed, networkStatus, optimizationFitness } = dashboardStats

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header */}
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your routing network, fleet operations, and optimization performance."
      />

      {/* 2. Responsive 4-Column KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6">
        {/* KPI 1: Active Vehicles */}
        <StatCard
          title={activeVehicles.label}
          value={activeVehicles.value}
          subtitle={activeVehicles.subtitle}
          accentColor={activeVehicles.accentColor}
          icon={<FleetIcon className="w-4 h-4" />}
        />

        {/* KPI 2: Total Customers Served */}
        <StatCard
          title={customersServed.label}
          value={customersServed.value}
          subtitle={customersServed.subtitle}
          accentColor={customersServed.accentColor}
          icon={<NetworkIcon className="w-4 h-4" />}
        />

        {/* KPI 3: Network Status */}
        <StatCard
          title={networkStatus.label}
          value={networkStatus.value}
          subtitle={networkStatus.subtitle}
          accentColor={networkStatus.accentColor}
          icon={<MapPinIcon className="w-4 h-4" />}
        />

        {/* KPI 4: Last Optimization Fitness */}
        <StatCard
          title={optimizationFitness.label}
          value={optimizationFitness.value}
          valueColor="text-emerald-400"
          subtitle={optimizationFitness.subtitle}
          badge={
            optimizationFitness.isFeasible ? (
              <Badge variant="success" size="sm" dot>
                Feasible
              </Badge>
            ) : null
          }
          accentColor={optimizationFitness.accentColor}
          icon={<OptimizeIcon className="w-4 h-4" />}
        />
      </div>

      {/* 3. Balanced 2-Column Section (Network Preview + Convergence Preview) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        <NetworkPreview networkData={networkPreviewData} />
        <ConvergencePreview convergenceData={convergenceData} />
      </div>

      {/* 4. Full-Width Recent Activity Feed */}
      <RecentActivity events={recentActivity} />
    </div>
  )
}

export default Dashboard
