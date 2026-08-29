import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Badge } from '../ui/Badge.jsx'

export function OptimizationDetailsCard({ analyticsData }) {
  const hasData = analyticsData != null
  const history = analyticsData?.history || []
  const initialFitness = history[0]?.fitness
  const finalFitness = analyticsData?.best_fitness ?? history[history.length - 1]?.fitness
  const nIterations = analyticsData?.n_iterations ?? 0
  const stoppedEarly = Boolean(analyticsData?.stopped_early)

  const reduction =
    initialFitness != null && finalFitness != null && initialFitness >= finalFitness
      ? (initialFitness - finalFitness).toFixed(1)
      : '—'

  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Optimization Details &amp; Telemetry Analysis</CardTitle>
          <CardDescription>
            Objective function interpretation, algorithmic properties, and swarm convergence telemetry
          </CardDescription>
        </div>

        <Badge variant="neutral" size="sm">
          QPSO Algorithm
        </Badge>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-5 sm:p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs sm:text-sm">
          {/* Section 1: Objective Formulation */}
          <div className="space-y-3">
            <h4 className="font-semibold text-slate-200 uppercase tracking-wider text-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              Fitness Function Formulation
            </h4>
            <div className="space-y-2 text-slate-400 leading-relaxed">
              <p>
                The QPSO solver minimizes a multi-objective cost penalty composed of weighted components:
              </p>
              <ul className="list-disc list-inside space-y-1 text-slate-300 font-mono text-[11px]">
                <li><strong className="text-slate-100">Travel Time:</strong> Primary transit delay penalty</li>
                <li><strong className="text-slate-100">Distance:</strong> Spatial route length minimization</li>
                <li><strong className="text-slate-100">Congestion:</strong> Real-time bottleneck factor</li>
              </ul>
              <p className="text-[11px] text-slate-500 pt-1">
                Lower fitness corresponds directly to more cost-effective fleet routing schedules.
              </p>
            </div>
          </div>

          {/* Section 2: Convergence Metrics */}
          <div className="space-y-3">
            <h4 className="font-semibold text-slate-200 uppercase tracking-wider text-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              Convergence Metrics
            </h4>
            <div className="space-y-2 text-slate-400">
              <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                <span>Baseline Score:</span>
                <span className="font-mono text-slate-200">
                  {initialFitness != null ? Number(initialFitness).toFixed(1) : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                <span>Global Optimum:</span>
                <span className="font-mono text-emerald-400 font-bold">
                  {finalFitness != null ? Number(finalFitness).toFixed(1) : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                <span>Total Fitness Delta:</span>
                <span className="font-mono text-purple-400 font-bold">
                  {reduction !== '—' ? `−${reduction}` : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span>Telemetry Samples:</span>
                <span className="font-mono text-slate-300">
                  {hasData ? `${history.length} checkpoints` : '0 points'}
                </span>
              </div>
            </div>
          </div>

          {/* Section 3: Algorithmic Architecture */}
          <div className="space-y-3">
            <h4 className="font-semibold text-slate-200 uppercase tracking-wider text-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-purple-400" />
              Solver Pipeline &amp; Search Space
            </h4>
            <div className="space-y-2 text-slate-400 leading-relaxed">
              <div>
                <strong className="text-slate-200">Search Horizon:</strong>{' '}
                <span className="font-mono text-slate-300">{nIterations} iterations</span>
                {stoppedEarly && (
                  <span className="text-amber-400 ml-1">(terminated early upon delta convergence)</span>
                )}
              </div>
              <div>
                <strong className="text-slate-200">Continuous to Discrete:</strong> Swarm position states are mapped into valid customer sequence permutations.
              </div>
              <div>
                <strong className="text-slate-200">Local Search:</strong> 2-opt post-repair heuristics eliminate path crossovers and enforce fleet capacity limits.
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default OptimizationDetailsCard
