import { StatCard } from '../dashboard/StatCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { OptimizeIcon, ClockIcon, CheckCircleIcon, RoutesIcon } from '../common/Icons.jsx'

export function OptimizationSummaryCards({ result }) {
  const hasResult = result != null
  const bestFitness = hasResult ? Number(result.best_fitness).toFixed(1) : '—'
  const iterationsRun = hasResult ? result.n_iterations_run : 0
  const isFeasible = hasResult ? Boolean(result.is_feasible) : false
  const nRoutes = hasResult ? result.n_routes : 0
  const stoppedEarly = hasResult ? Boolean(result.stopped_early) : false

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6 w-full">
      {/* 1. Best Fitness */}
      <StatCard
        title="Best Fitness"
        value={hasResult ? bestFitness : 'No Run'}
        valueColor={hasResult ? 'text-emerald-400' : 'text-slate-500'}
        subtitle={
          hasResult
            ? 'Global minimized objective score'
            : 'Awaiting QPSO solver execution'
        }
        accentColor="green"
        icon={<OptimizeIcon className="w-4 h-4" />}
      />

      {/* 2. Iterations Run */}
      <StatCard
        title="Iterations Run"
        value={hasResult ? `${iterationsRun} Iter` : '0 Iter'}
        subtitle={
          hasResult
            ? stoppedEarly
              ? 'Stopped early upon convergence'
              : 'Completed full search horizon'
            : 'No swarm steps performed'
        }
        accentColor="blue"
        icon={<ClockIcon className="w-4 h-4" />}
      />

      {/* 3. Feasibility */}
      <StatCard
        title="Solution Feasibility"
        value={
          hasResult
            ? isFeasible
              ? 'FEASIBLE'
              : 'INFEASIBLE'
            : 'Unvalidated'
        }
        valueColor={
          hasResult
            ? isFeasible
              ? 'text-emerald-400'
              : 'text-rose-400'
            : 'text-slate-500'
        }
        subtitle={
          hasResult
            ? isFeasible
              ? 'Capacity & route constraints satisfied'
              : 'Route capacity violations present'
            : 'Requires optimizer validation'
        }
        badge={
          hasResult ? (
            isFeasible ? (
              <Badge variant="success" size="sm" dot>
                Feasible
              </Badge>
            ) : (
              <Badge variant="danger" size="sm" dot>
                Infeasible
              </Badge>
            )
          ) : (
            <Badge variant="neutral" size="sm">
              Idle
            </Badge>
          )
        }
        accentColor={hasResult ? (isFeasible ? 'green' : 'rose') : 'amber'}
        icon={<CheckCircleIcon className="w-4 h-4" />}
      />

      {/* 4. Routes Generated */}
      <StatCard
        title="Routes Generated"
        value={hasResult ? `${nRoutes} Routes` : '0 Routes'}
        subtitle={
          hasResult
            ? 'Optimized vehicle schedules generated'
            : 'No routes computed yet'
        }
        accentColor="purple"
        icon={<RoutesIcon className="w-4 h-4" />}
      />
    </div>
  )
}

export default OptimizationSummaryCards
