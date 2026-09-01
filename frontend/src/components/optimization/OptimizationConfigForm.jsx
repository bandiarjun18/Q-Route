import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Input } from '../ui/Input.jsx'
import { OptimizeIcon, RefreshIcon } from '../common/Icons.jsx'

export function OptimizationConfigForm({
  params,
  onChangeParam,
  onApplyPreset,
  onRunOptimization,
  onResetDefaults,
  isLoading,
  error,
}) {
  const handlePresetSelect = (e) => {
    const preset = e.target.value
    if (preset === 'fast') {
      onApplyPreset({
        n_particles: 15,
        max_iterations: 50,
        time_budget_seconds: '',
        seed: 42,
        w_time: 1.0,
        w_distance: 0.5,
        w_congestion: 0.3,
      })
    } else if (preset === 'standard') {
      onApplyPreset({
        n_particles: 20,
        max_iterations: 100,
        time_budget_seconds: '',
        seed: 42,
        w_time: 1.0,
        w_distance: 0.5,
        w_congestion: 0.3,
      })
    } else if (preset === 'precision') {
      onApplyPreset({
        n_particles: 40,
        max_iterations: 250,
        time_budget_seconds: '10.0',
        seed: 42,
        w_time: 1.2,
        w_distance: 0.6,
        w_congestion: 0.4,
      })
    }
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div>
          <CardTitle>Optimization Configuration</CardTitle>
          <CardDescription>
            Configure the QPSO parameters used to generate optimized vehicle routes.
          </CardDescription>
        </div>

        {/* Preset Selector */}
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-slate-400 font-medium hidden sm:inline">Solver Preset:</span>
          <select
            aria-label="Optimization solver preset"
            onChange={handlePresetSelect}
            defaultValue="standard"
            disabled={isLoading}
            className="h-8 bg-slate-950 border border-slate-800 rounded-lg px-2.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
          >
            <option value="fast">Fast Solver (15 particles, 50 iter)</option>
            <option value="standard">Standard Solver (20 particles, 100 iter)</option>
            <option value="precision">High Precision (40 particles, 250 iter)</option>
          </select>
        </div>
      </CardHeader>

      <CardContent className="p-5 sm:p-6 space-y-5">
        {/* Error Feedback */}
        {error && (
          <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="font-semibold">Optimization Failed:</span>
              <span className="truncate">{error}</span>
            </div>
            <Button variant="danger" size="sm" onClick={onRunOptimization} className="shrink-0 h-7 text-xs px-2.5">
              Try Again
            </Button>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            onRunOptimization()
          }}
          className="space-y-6"
        >
          {/* Swarm & Execution Parameters */}
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
              Swarm &amp; Execution Controls
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Input
                label="Swarm Size (Particles)"
                type="number"
                min="2"
                max="200"
                value={params.n_particles}
                onChange={(e) => onChangeParam('n_particles', e.target.value)}
                helperText="Minimum 2 particles (default 20)"
                required
                disabled={isLoading}
              />

              <Input
                label="Max Iterations"
                type="number"
                min="1"
                max="2000"
                value={params.max_iterations}
                onChange={(e) => onChangeParam('max_iterations', e.target.value)}
                helperText="Search step limit (default 100)"
                required
                disabled={isLoading}
              />

              <Input
                label="Time Budget (Seconds)"
                type="number"
                step="0.1"
                min="0.1"
                value={params.time_budget_seconds ?? ''}
                onChange={(e) => onChangeParam('time_budget_seconds', e.target.value)}
                helperText="Optional wall-clock limit"
                placeholder="Unlimited"
                disabled={isLoading}
              />

              <Input
                label="RNG Seed"
                type="number"
                value={params.seed}
                onChange={(e) => onChangeParam('seed', e.target.value)}
                helperText="Deterministic solver seed"
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Objective Fitness Weights */}
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              Multi-Objective Fitness Weights
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Input
                label="Travel Time Weight (w_time)"
                type="number"
                step="0.1"
                min="0.1"
                value={params.w_time}
                onChange={(e) => onChangeParam('w_time', e.target.value)}
                helperText="Primary travel duration cost (> 0)"
                required
                disabled={isLoading}
              />

              <Input
                label="Distance Weight (w_distance)"
                type="number"
                step="0.1"
                min="0.1"
                value={params.w_distance}
                onChange={(e) => onChangeParam('w_distance', e.target.value)}
                helperText="Total route length cost (> 0)"
                required
                disabled={isLoading}
              />

              <Input
                label="Congestion Weight (w_congestion)"
                type="number"
                step="0.1"
                min="0"
                value={params.w_congestion}
                onChange={(e) => onChangeParam('w_congestion', e.target.value)}
                helperText="Traffic bottleneck penalty (≥ 0)"
                required
                disabled={isLoading}
              />

              <div className="flex flex-col justify-end space-y-1.5 pt-1">
                <span className="block text-xs font-medium text-slate-400 select-none hidden sm:block">
                  Actions
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    isLoading={isLoading}
                    leftIcon={<OptimizeIcon className="w-4 h-4" />}
                    className="flex-1 font-semibold"
                  >
                    {isLoading ? 'Running QPSO...' : 'Run Optimization'}
                  </Button>

                  <Button
                    type="button"
                    variant="secondary"
                    size="md"
                    onClick={onResetDefaults}
                    disabled={isLoading}
                    className="px-3"
                    title="Reset default parameters"
                    aria-label="Reset default parameters"
                  >
                    <RefreshIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

export default OptimizationConfigForm
