import { StatCard } from '../dashboard/StatCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { OptimizeIcon, ClockIcon, CheckCircleIcon, AnalyticsIcon } from '../common/Icons.jsx'

export function AnalyticsSummaryCards({ analyticsData }) {
  const hasData = analyticsData != null && analyticsData.history?.length > 0
  const history = analyticsData?.history || []
  const bestFitness = hasData ? Number(analyticsData.best_fitness).toFixed(1) : '—'
  const iterationsRun = hasData ? analyticsData.n_iterations : 0
  const stoppedEarly = hasData ? Boolean(analyticsData.stopped_early) : false

  const initialFitness = hasData && history.length > 0 ? history[0].fitness : null
  const finalFitness = hasData && history.length > 0 ? history[history.length - 1].fitness : null
  const reduction =
    initialFitness != null && finalFitness != null && initialFitness >= finalFitness
      ? (initialFitness - finalFitness).toFixed(1)
      : null
  const reductionPct =
    initialFitness != null && finalFitness != null && initialFitness > 0
      ? (((initialFitness - finalFitness) / initialFitness) * 100).toFixed(1)
      : null

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-6 w-full">
      {/* 1. Best Fitness */}
      <StatCard
        title="Best Fitness"
        value={hasData ? bestFitness : 'No Data'}
        valueColor={hasData ? 'text-emerald-400' : 'text-slate-500'}
        subtitle={
          hasData
            ? 'Global minimized objective score'
            : 'Awaiting QPSO solver execution'
        }
        accentColor="green"
        icon={<OptimizeIcon className="w-4 h-4" />}
      />

      {/* 2. Iterations Run */}
      <StatCard
        title="Iterations Run"
        value={hasData ? `${iterationsRun} Iter` : '0 Iter'}
        subtitle={
          hasData
            ? `${history.length} convergence checkpoints recorded`
            : 'No swarm iterations recorded'
        }
        accentColor="blue"
        icon={<ClockIcon className="w-4 h-4" />}
      />

      {/* 3. Optimization Status */}
      <StatCard
        title="Optimization Status"
        value={hasData ? (stoppedEarly ? 'Stopped Early' : 'Completed') : 'Idle'}
        valueColor={hasData ? (stoppedEarly ? 'text-amber-400' : 'text-emerald-400') : 'text-slate-500'}
        subtitle={
          hasData
            ? stoppedEarly
              ? 'Early convergence threshold reached'
              : 'Completed full search horizon'
            : 'No solver runs logged'
        }
        badge={
          hasData ? (
            stoppedEarly ? (
              <Badge variant="warning" size="sm" dot>
                Stopped Early
              </Badge>
            ) : (
              <Badge variant="success" size="sm" dot>
                Completed
              </Badge>
            )
          ) : (
            <Badge variant="neutral" size="sm">
              Idle
            </Badge>
          )
        }
        accentColor={hasData ? (stoppedEarly ? 'amber' : 'green') : 'neutral'}
        icon={stoppedEarly ? <ClockIcon className="w-4 h-4" /> : <CheckCircleIcon className="w-4 h-4" />}
      />

      {/* 4. Fitness Reduction */}
      <StatCard
        title="Fitness Improvement"
        value={
          hasData && reduction != null
            ? `−${reduction}`
            : '—'
        }
        valueColor={hasData && reduction != null ? 'text-purple-400' : 'text-slate-500'}
        subtitle={
          hasData && reductionPct != null
            ? `${reductionPct}% reduction from initial swarm state`
            : 'Awaiting baseline telemetry'
        }
        badge={
          hasData && reductionPct != null ? (
            <Badge variant="info" size="sm">
              {reductionPct}% Imp
            </Badge>
          ) : null
        }
        accentColor="purple"
        icon={<AnalyticsIcon className="w-4 h-4" />}
      />
    </div>
  )
}

export default AnalyticsSummaryCards
