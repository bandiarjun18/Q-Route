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
import { OptimizeIcon, ArrowRightIcon } from '../common/Icons.jsx'

export function ConvergencePreview({ convergenceData = [], className = '' }) {
  const navigate = useNavigate()

  const history = convergenceData || []
  const initialFitness = history[0]?.fitness
  const bestFitness = history[history.length - 1]?.fitness

  return (
    <Card className={`flex flex-col justify-between h-full ${className}`}>
      {/* Card Header */}
      <CardHeader>
        <div>
          <CardTitle>Convergence Trajectory</CardTitle>
          <CardDescription>
            Swarm fitness minimization history
          </CardDescription>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="text-xs h-8 px-3"
          rightIcon={<ArrowRightIcon className="w-3.5 h-3.5" />}
          onClick={() => navigate('/analytics')}
        >
          View Full Analytics
        </Button>
      </CardHeader>

      {/* Card Content */}
      <CardContent className="p-4 sm:p-5 flex-1 flex flex-col justify-center">
        <div className="w-full h-[340px] sm:h-[360px] rounded-xl bg-slate-950/90 border border-slate-800/80 p-4 sm:p-5 flex flex-col justify-between select-none">
          {history.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blue-400 shadow-xs">
                <OptimizeIcon className="w-6 h-6" />
              </div>

              <div className="space-y-1.5 max-w-xs">
                <h3 className="text-base font-semibold text-slate-100">
                  No optimization data yet
                </h3>
                <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                  Execute the QPSO solver to compute vehicle routes and record convergence telemetry.
                </p>
              </div>

              <div className="pt-1">
                <Button variant="primary" size="md" onClick={() => navigate('/optimization')}>
                  Run Optimization
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Top Status Metric Row */}
              <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-slate-800/80 mb-2">
                <span>QPSO Swarm Minimization ({history.length} Checkpoints)</span>
                <div className="flex items-center gap-3">
                  {initialFitness != null && (
                    <span>
                      Init: <strong className="text-slate-200 font-mono">{initialFitness.toFixed(1)}</strong>
                    </span>
                  )}
                  {bestFitness != null && (
                    <span className="text-emerald-400">
                      Best: <strong className="font-mono">{bestFitness.toFixed(1)}</strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Recharts Responsive Container */}
              <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={history}
                    margin={{ top: 10, right: 15, left: -10, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="iteration"
                      stroke="#64748b"
                      fontSize={11}
                      tickFormatter={(val) => `Iter ${val}`}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={11}
                      domain={['auto', 'auto']}
                      tickFormatter={(val) => Number(val).toFixed(0)}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        borderColor: '#334155',
                        borderRadius: '0.5rem',
                        fontSize: '12px',
                        color: '#f8fafc',
                        padding: '8px 12px',
                      }}
                      formatter={(val) => [`${Number(val).toFixed(2)}`, 'Fitness Objective']}
                      labelFormatter={(label) => `Iteration #${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="fitness"
                      stroke="#3b82f6"
                      strokeWidth={2.5}
                      dot={false}
                      activeDot={{ r: 4, fill: '#60a5fa' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Bottom Footnote */}
              <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-800/80 mt-1">
                <span>Objective Fitness Minimization</span>
                <span className="font-mono">Iter 1 → Iter {history[history.length - 1]?.iteration || 50}</span>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default ConvergencePreview
