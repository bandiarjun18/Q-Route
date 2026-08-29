import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { FleetIcon, UsersIcon, CheckCircleIcon, RefreshIcon } from '../common/Icons.jsx'

export function FleetConfigCard({
  onOpenAddVehicle,
  onOpenAddCustomer,
  onApplyPreset,
  onSubmitFleet,
  onResetFleet,
  isLoading,
  error,
  successMessage,
  vehiclesCount,
  customersCount,
}) {
  const handlePresetSelect = (e) => {
    const preset = e.target.value
    if (preset === 'small') {
      onApplyPreset({
        vehicles: [
          { vehicle_id: 0, capacity: 50.0, depot_node: 0 },
          { vehicle_id: 1, capacity: 50.0, depot_node: 0 },
        ],
        customers: [
          { customer_id: 0, location_node: 3, demand: 8.5 },
          { customer_id: 1, location_node: 7, demand: 6.0 },
          { customer_id: 2, location_node: 11, demand: 4.2 },
        ],
      })
    } else if (preset === 'standard') {
      onApplyPreset({
        vehicles: [
          { vehicle_id: 0, capacity: 60.0, depot_node: 0 },
          { vehicle_id: 1, capacity: 60.0, depot_node: 0 },
          { vehicle_id: 2, capacity: 60.0, depot_node: 0 },
          { vehicle_id: 3, capacity: 60.0, depot_node: 0 },
        ],
        customers: [
          { customer_id: 0, location_node: 1, demand: 12.0 },
          { customer_id: 1, location_node: 2, demand: 15.0 },
          { customer_id: 2, location_node: 3, demand: 8.5 },
          { customer_id: 3, location_node: 4, demand: 14.0 },
          { customer_id: 4, location_node: 5, demand: 9.0 },
          { customer_id: 5, location_node: 6, demand: 11.5 },
        ],
      })
    } else if (preset === 'heavy') {
      onApplyPreset({
        vehicles: [
          { vehicle_id: 0, capacity: 75.0, depot_node: 0 },
          { vehicle_id: 1, capacity: 75.0, depot_node: 0 },
          { vehicle_id: 2, capacity: 75.0, depot_node: 0 },
          { vehicle_id: 3, capacity: 75.0, depot_node: 0 },
          { vehicle_id: 4, capacity: 75.0, depot_node: 0 },
          { vehicle_id: 5, capacity: 75.0, depot_node: 0 },
        ],
        customers: [
          { customer_id: 0, location_node: 1, demand: 14.0 },
          { customer_id: 1, location_node: 2, demand: 18.0 },
          { customer_id: 2, location_node: 3, demand: 10.0 },
          { customer_id: 3, location_node: 4, demand: 16.0 },
          { customer_id: 4, location_node: 5, demand: 12.0 },
          { customer_id: 5, location_node: 6, demand: 20.0 },
          { customer_id: 6, location_node: 7, demand: 11.0 },
          { customer_id: 7, location_node: 8, demand: 15.0 },
        ],
      })
    }
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div>
          <CardTitle>Fleet Configuration</CardTitle>
          <CardDescription>
            Configure vehicles and customer delivery demand before running route optimization.
          </CardDescription>
        </div>

        {/* Preset Selector */}
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-slate-400 font-medium hidden sm:inline">Load Preset:</span>
          <select
            aria-label="Load fleet preset"
            onChange={handlePresetSelect}
            defaultValue="small"
            disabled={isLoading}
            className="h-8 bg-slate-950 border border-slate-800 rounded-lg px-2.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
          >
            <option value="small">Small Fleet (2 Veh / 3 Cust)</option>
            <option value="standard">Standard Fleet (4 Veh / 6 Cust)</option>
            <option value="heavy">Heavy Fleet (6 Veh / 8 Cust)</option>
          </select>
        </div>
      </CardHeader>

      <CardContent className="p-5 sm:p-6 space-y-4">
        {/* Error Feedback */}
        {error && (
          <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="font-semibold">Configuration Error:</span>
              <span className="truncate">{error}</span>
            </div>
            <Button variant="danger" size="sm" onClick={onSubmitFleet} className="shrink-0 h-7 text-xs px-2.5">
              Retry
            </Button>
          </div>
        )}

        {/* Success Feedback */}
        {successMessage && !error && (
          <div className="p-3.5 bg-emerald-950/80 border border-emerald-800/80 rounded-lg text-emerald-300 text-xs sm:text-sm flex items-center gap-2.5">
            <CheckCircleIcon className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Action Controls Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              type="button"
              variant="secondary"
              size="md"
              leftIcon={<FleetIcon className="w-4 h-4" />}
              onClick={onOpenAddVehicle}
              disabled={isLoading}
            >
              Add Vehicle
            </Button>

            <Button
              type="button"
              variant="secondary"
              size="md"
              leftIcon={<UsersIcon className="w-4 h-4" />}
              onClick={onOpenAddCustomer}
              disabled={isLoading}
            >
              Add Customer Order
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={onResetFleet}
              disabled={isLoading}
              className="text-slate-400 hover:text-slate-200 border border-slate-800 bg-slate-900/40"
              leftIcon={<RefreshIcon className="w-4 h-4" />}
            >
              Clear All
            </Button>
          </div>

          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={onSubmitFleet}
            isLoading={isLoading}
            disabled={vehiclesCount === 0 || customersCount === 0}
            className="font-semibold px-5"
          >
            {isLoading ? 'Submitting Fleet...' : 'Save Fleet Configuration (POST /fleet)'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default FleetConfigCard
