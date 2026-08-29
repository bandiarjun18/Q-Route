import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Input } from '../ui/Input.jsx'
import { NetworkIcon, RefreshIcon } from '../common/Icons.jsx'

export function NetworkConfigForm({
  params,
  onChangeParam,
  onApplyPreset,
  onGenerate,
  onResetDefaults,
  isLoading,
  error,
}) {
  const handlePresetChange = (e) => {
    const preset = e.target.value
    if (preset === 'small') {
      onApplyPreset({
        n_nodes: 12,
        n_depots: 1,
        n_customers: 4,
        connect_radius_km: 4.0,
        grid_size_km: 8.0,
        closed_fraction: 0.0,
        seed: 42,
      })
    } else if (preset === 'standard') {
      onApplyPreset({
        n_nodes: 20,
        n_depots: 1,
        n_customers: 6,
        connect_radius_km: 3.5,
        grid_size_km: 10.0,
        closed_fraction: 0.05,
        seed: 42,
      })
    } else if (preset === 'large') {
      onApplyPreset({
        n_nodes: 36,
        n_depots: 2,
        n_customers: 12,
        connect_radius_km: 3.0,
        grid_size_km: 15.0,
        closed_fraction: 0.08,
        seed: 101,
      })
    }
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div>
          <CardTitle>Network Configuration</CardTitle>
          <CardDescription>
            Generate a synthetic transportation network for route optimization.
          </CardDescription>
        </div>

        {/* Preset Selector */}
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-slate-400 font-medium hidden sm:inline">Preset:</span>
          <select
            aria-label="Preset configuration"
            onChange={handlePresetChange}
            defaultValue="standard"
            disabled={isLoading}
            className="h-8 bg-slate-950 border border-slate-800 rounded-lg px-2.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
          >
            <option value="small">Small Network (12 Nodes)</option>
            <option value="standard">Standard Network (20 Nodes)</option>
            <option value="large">Large Network (36 Nodes)</option>
          </select>
        </div>
      </CardHeader>

      <CardContent className="p-5 sm:p-6 space-y-5">
        {/* Error Alert if Generation Failed */}
        {error && (
          <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="font-semibold">Generation Failed:</span>
              <span className="truncate">{error}</span>
            </div>
            <Button variant="danger" size="sm" onClick={onGenerate} className="shrink-0 h-7 text-xs px-2.5">
              Retry
            </Button>
          </div>
        )}

        {/* Form Inputs Grid */}
        <form
          onSubmit={(e) => {
            e.preventDefault()
            onGenerate()
          }}
          className="space-y-5"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Input
              label="Total Nodes"
              type="number"
              min="4"
              max="100"
              value={params.n_nodes}
              onChange={(e) => onChangeParam('n_nodes', e.target.value)}
              helperText="Minimum 4 nodes"
              required
              disabled={isLoading}
            />

            <Input
              label="Depot Count"
              type="number"
              min="1"
              max="5"
              value={params.n_depots}
              onChange={(e) => onChangeParam('n_depots', e.target.value)}
              helperText="Starting dispatch depots"
              required
              disabled={isLoading}
            />

            <Input
              label="Customer Nodes"
              type="number"
              min="1"
              max={Math.max(1, Number(params.n_nodes) - Number(params.n_depots))}
              value={params.n_customers}
              onChange={(e) => onChangeParam('n_customers', e.target.value)}
              helperText="Delivery dropoff locations"
              required
              disabled={isLoading}
            />

            <Input
              label="Connection Radius (km)"
              type="number"
              step="0.1"
              min="1.0"
              max="20.0"
              value={params.connect_radius_km}
              onChange={(e) => onChangeParam('connect_radius_km', e.target.value)}
              helperText="Max edge proximity threshold"
              required
              disabled={isLoading}
            />

            <Input
              label="Grid Size (km)"
              type="number"
              step="0.5"
              min="5.0"
              max="50.0"
              value={params.grid_size_km}
              onChange={(e) => onChangeParam('grid_size_km', e.target.value)}
              helperText="Square spatial boundary"
              required
              disabled={isLoading}
            />

            <Input
              label="Closed Road Fraction"
              type="number"
              step="0.01"
              min="0"
              max="0.5"
              value={params.closed_fraction}
              onChange={(e) => onChangeParam('closed_fraction', e.target.value)}
              helperText="0.0 to 0.5 disruption rate"
              disabled={isLoading}
            />

            <Input
              label="Random Seed"
              type="number"
              value={params.seed}
              onChange={(e) => onChangeParam('seed', e.target.value)}
              helperText="Reproducible topology seed"
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
                  leftIcon={<NetworkIcon className="w-4 h-4" />}
                  className="flex-1 font-semibold"
                >
                  {isLoading ? 'Generating...' : 'Generate Network'}
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
        </form>
      </CardContent>
    </Card>
  )
}

export default NetworkConfigForm
