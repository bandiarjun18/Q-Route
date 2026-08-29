import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../ui/Table.jsx'
import { OptimizeIcon, ArrowRightIcon, CheckCircleIcon, FleetIcon } from '../common/Icons.jsx'

export function OptimizationResultCard({ result, isLoading, onRunOptimization }) {
  const navigate = useNavigate()

  const preRepair = result?.pre_repair_fitness != null ? Number(result.pre_repair_fitness).toFixed(1) : 'Not available'
  const postRepair = result?.post_repair_fitness != null ? Number(result.post_repair_fitness).toFixed(1) : 'Not available'
  const bestFitness = result?.best_fitness != null ? Number(result.best_fitness).toFixed(1) : 'Not available'
  const routes = result?.routes || []

  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Optimization Result</CardTitle>
          <CardDescription>
            Execution status, fitness progression, and vehicle schedule breakdown
          </CardDescription>
        </div>

        {result && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/routes')}
            rightIcon={<ArrowRightIcon className="w-3.5 h-3.5" />}
            className="font-semibold text-xs h-8 px-3"
          >
            View Live Routes →
          </Button>
        )}
      </CardHeader>

      {/* Content */}
      <CardContent className="p-5 sm:p-6 space-y-6">
        {isLoading ? (
          <div className="py-12 px-6 text-center space-y-4 flex flex-col items-center justify-center">
            <div className="w-12 h-12 rounded-full border-3 border-blue-500/20 border-t-blue-500 animate-spin" />
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-100">
                Optimization in progress
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
                Running Quantum Particle Swarm Optimization (QPSO), discrete particle sampling, and 2-opt capacity repair...
              </p>
            </div>
          </div>
        ) : !result ? (
          <div className="py-10 px-6 text-center space-y-3 flex flex-col items-center justify-center">
            <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-blue-400">
              <OptimizeIcon className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-100">
                No optimization run yet
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
                Configure the QPSO parameters above and run optimization to compute multi-vehicle routes.
              </p>
            </div>
            <div className="pt-1">
              <Button variant="primary" size="md" onClick={onRunOptimization} leftIcon={<OptimizeIcon className="w-4 h-4" />}>
                Run Optimization
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Success Banner */}
            <div className="p-4 rounded-xl bg-emerald-950/70 border border-emerald-800/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-emerald-200 text-xs sm:text-sm">
              <div className="flex items-center gap-3">
                <CheckCircleIcon className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <span className="font-semibold text-emerald-100">
                    Optimization complete:
                  </span>{' '}
                  <span>
                    Successfully solved in {result.n_iterations_run} iterations with best fitness {bestFitness}. Routes are ready for dispatch.
                  </span>
                </div>
              </div>

              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/routes')}
                rightIcon={<ArrowRightIcon className="w-3.5 h-3.5" />}
                className="shrink-0 h-8 text-xs font-semibold px-3 bg-emerald-600 hover:bg-emerald-500 border-emerald-500/30 text-white"
              >
                View Live Routes →
              </Button>
            </div>

            {/* Fitness Progression Metrics */}
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                Fitness Progression &amp; Repair Telemetry
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <span className="text-xs text-slate-500 font-medium">Pre-Repair Fitness</span>
                  <div className="text-lg font-bold font-mono text-slate-300">{preRepair}</div>
                  <span className="text-[11px] text-slate-500">Raw particle position score</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <span className="text-xs text-slate-500 font-medium">Post-Repair Fitness</span>
                  <div className="text-lg font-bold font-mono text-blue-400">{postRepair}</div>
                  <span className="text-[11px] text-slate-500">Post capacity-feasibility repair</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <span className="text-xs text-slate-500 font-medium">Best Objective Score</span>
                  <div className="text-lg font-bold font-mono text-emerald-400">{bestFitness}</div>
                  <span className="text-[11px] text-slate-500">Final 2-opt local search optimum</span>
                </div>
              </div>
            </div>

            {/* Computed Vehicle Routes Breakdown */}
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                Computed Vehicle Schedules ({routes.length} Active Routes)
              </h4>

              {routes.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Vehicle</TableHead>
                      <TableHead>Depot</TableHead>
                      <TableHead>Delivery Stops</TableHead>
                      <TableHead>Travel Distance</TableHead>
                      <TableHead>Travel Time</TableHead>
                      <TableHead>Full Node Sequence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {routes.map((route, idx) => (
                      <TableRow key={route.vehicle_id ?? idx}>
                        <TableCell className="font-semibold text-slate-100 font-mono">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-md bg-blue-950/80 border border-blue-800/60 flex items-center justify-center text-blue-400 text-xs">
                              <FleetIcon className="w-3 h-3" />
                            </div>
                            <span>VEHICLE #{route.vehicle_id}</span>
                          </div>
                        </TableCell>

                        <TableCell className="font-mono text-slate-300">
                          <Badge variant="neutral" size="sm">
                            Depot #{route.depot_node}
                          </Badge>
                        </TableCell>

                        <TableCell className="font-mono text-slate-200">
                          <span className="font-bold text-slate-100">{route.visit_order?.length || 0}</span> customers
                        </TableCell>

                        <TableCell className="font-mono text-slate-200">
                          <span className="font-bold text-slate-100">{Number(route.total_distance).toFixed(1)}</span> km
                        </TableCell>

                        <TableCell className="font-mono text-slate-200">
                          <span className="font-bold text-slate-100">{Number(route.total_travel_time).toFixed(1)}</span> min
                        </TableCell>

                        <TableCell className="font-mono text-slate-400 text-xs truncate max-w-xs">
                          {route.node_sequence ? route.node_sequence.join(' → ') : '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl text-center text-xs text-slate-500">
                  No individual route paths returned.
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default OptimizationResultCard
