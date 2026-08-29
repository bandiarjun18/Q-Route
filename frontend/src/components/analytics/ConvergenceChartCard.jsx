import { useNavigate } from 'react-router-dom'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { OptimizeIcon, AnalyticsIcon } from '../common/Icons.jsx'

export function ConvergenceChartCard({ analyticsData, isLoading }) {
  const navigate = useNavigate()

  // Ensure history is sorted by iteration ascending
  const rawHistory = analyticsData?.history || []
  const history = [...rawHistory].sort((a, b) => Number(a.iteration) - Number(b.iteration))

  const initialFitness = history[0]?.fitness
  const bestFitness = analyticsData?.best_fitness ?? history[history.length - 1]?.fitness

  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>QPSO Convergence</CardTitle>
          <CardDescription>
            Global-best fitness minimization across swarm optimization iterations
          </CardDescription>
        </div>

        <div className="flex items-center gap-2">
          {history.length > 0 && (
            <Badge variant="info" size="sm">
              {history.length} Telemetry Checkpoints
            </Badge>
          )}
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-4 sm:p-6">
        <div className="relative w-full h-[400px] sm:h-[450px] lg:h-[480px] rounded-xl bg-slate-950/90 border border-slate-800/80 p-4 sm:p-6 flex flex-col justify-between select-none">
          {isLoading ? (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4">
              <div className="w-10 h-10 rounded-full border-3 border-blue-500/20 border-t-blue-500 animate-spin" />
              <p className="text-sm font-semibold text-slate-300">Loading optimization telemetry...</p>
            </div>
          ) : history.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blue-400 shadow-xs">
                <AnalyticsIcon className="w-7 h-7" />
              </div>

              <div className="space-y-1.5 max-w-sm">
                <h3 className="text-lg font-semibold text-slate-100">
                  No optimization analytics yet
                </h3>
                <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                  Execute the QPSO route optimizer to generate convergence trajectory curves and telemetry history.
                </p>
              </div>

              <div className="pt-2">
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => navigate('/optimization')}
                  leftIcon={<OptimizeIcon className="w-4 h-4" />}
                >
                  Run Optimization
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Top Telemetry Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 pb-3 border-b border-slate-800/80 mb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-400" />
                  <span className="font-semibold text-slate-200">Objective Minimization Trajectory</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-400 font-mono">
                    Span: Iteration 0 → {history[history.length - 1]?.iteration}
                  </span>
                </div>

                <div className="flex items-center gap-4 font-mono text-xs">
                  {initialFitness != null && (
                    <span className="text-slate-400">
                      Initial: <strong className="text-slate-200">{Number(initialFitness).toFixed(1)}</strong>
                    </span>
                  )}
                  {bestFitness != null && (
                    <span className="text-emerald-400">
                      Best: <strong className="text-emerald-300">{Number(bestFitness).toFixed(1)}</strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Responsive Recharts LineChart */}
              <div className="flex-1 w-full min-h-0 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={history}
                    margin={{ top: 15, right: 25, left: -5, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="iteration"
                      stroke="#64748b"
                      fontSize={11}
                      tickFormatter={(val) => `Iter ${val}`}
                      tickLine={{ stroke: '#334155' }}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={11}
                      domain={['auto', 'auto']}
                      tickFormatter={(val) => Number(val).toFixed(0)}
                      tickLine={{ stroke: '#334155' }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        borderColor: '#334155',
                        borderRadius: '0.75rem',
                        fontSize: '12px',
                        color: '#f8fafc',
                        padding: '10px 14px',
                        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
                      }}
                      formatter={(val) => [`${Number(val).toFixed(2)}`, 'Objective Fitness']}
                      labelFormatter={(label) => `Search Iteration #${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="fitness"
                      stroke="#3b82f6"
                      strokeWidth={3}
                      dot={false}
                      activeDot={{ r: 5, fill: '#60a5fa', stroke: '#1d4ed8', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Bottom Canvas Footer */}
              <div className="flex items-center justify-between text-xs text-slate-500 pt-3 border-t border-slate-800/80 mt-1">
                <span>Horizontal: Swarm Iterations · Vertical: Fitness Objective Score</span>
                <span className="font-mono text-slate-400">Non-increasing minimization curve</span>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default ConvergenceChartCard
