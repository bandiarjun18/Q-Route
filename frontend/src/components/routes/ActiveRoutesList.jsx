import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { FleetIcon, RoutesIcon, MapPinIcon, ClockIcon } from '../common/Icons.jsx'

export function ActiveRoutesList({ routes = [], selectedVehicleId, onSelectRoute }) {
  const navigate = useNavigate()

  return (
    <Card className="flex flex-col h-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Active Routes</CardTitle>
          <CardDescription>
            Currently registered vehicle routes
          </CardDescription>
        </div>

        <Badge variant="neutral" size="sm">
          {routes.length} Active
        </Badge>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-4 sm:p-5 flex-1 flex flex-col justify-start">
        {routes.length > 0 ? (
          <div className="space-y-3 overflow-y-auto max-h-[500px] pr-1">
            {routes.map((route) => {
              const isSelected = selectedVehicleId === route.vehicle_id
              const nStops = route.visit_order ? route.visit_order.length : 0
              const distance = Number(route.total_distance || 0).toFixed(1)
              const travelTime = Number(route.total_travel_time || 0).toFixed(1)
              const eta = route.estimated_arrival != null ? `${Number(route.estimated_arrival).toFixed(0)} min` : 'ETA —'
              const isAffected = route.status === 'AFFECTED'

              return (
                <div
                  key={route.vehicle_id}
                  onClick={() => onSelectRoute(route.vehicle_id)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer select-none space-y-3 ${
                    isSelected
                      ? 'bg-blue-950/40 border-blue-500 shadow-md ring-1 ring-blue-500/40'
                      : 'bg-slate-950/80 border-slate-800/90 hover:bg-slate-900/90 hover:border-slate-700'
                  }`}
                >
                  {/* Top Row: Vehicle ID & Status Badge */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs shrink-0 ${
                          isSelected
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-900 border border-slate-800 text-blue-400'
                        }`}
                      >
                        <FleetIcon className="w-3.5 h-3.5" />
                      </div>
                      <span className="font-semibold text-sm text-slate-100 font-mono">
                        VEHICLE #{route.vehicle_id}
                      </span>
                    </div>

                    <Badge
                      variant={isAffected ? 'warning' : 'success'}
                      size="sm"
                      dot
                    >
                      {isAffected ? 'AFFECTED' : 'ACTIVE'}
                    </Badge>
                  </div>

                  {/* Middle Row: Stops info */}
                  <div className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                    <span className="text-slate-300 font-semibold">{nStops} delivery stops</span>
                    <span className="text-slate-600">·</span>
                    <span>Depot #{route.depot_node}</span>
                  </div>

                  {/* Bottom Row: Metrics Breakdown */}
                  <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400 font-mono">
                    <div className="flex items-center gap-1">
                      <MapPinIcon className="w-3 h-3 text-slate-500" />
                      <span className="text-slate-200">{distance} km</span>
                    </div>

                    <div className="flex items-center gap-1">
                      <ClockIcon className="w-3 h-3 text-slate-500" />
                      <span className="text-slate-200">{travelTime} min</span>
                    </div>

                    <div className="text-blue-400 font-semibold">
                      {eta}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="h-[380px] flex flex-col items-center justify-center p-6 text-center space-y-3">
            <div className="w-10 h-10 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-blue-400">
              <RoutesIcon className="w-5 h-5" />
            </div>
            <div className="space-y-1 max-w-xs">
              <h4 className="text-sm font-semibold text-slate-200">No active routes</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Run route optimization to generate active vehicle routes across the network.
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/optimization')}
              leftIcon={<RoutesIcon className="w-3.5 h-3.5" />}
            >
              Run Optimization
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default ActiveRoutesList
