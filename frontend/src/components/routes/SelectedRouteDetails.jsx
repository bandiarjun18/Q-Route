import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Badge } from '../ui/Badge.jsx'
import { FleetIcon } from '../common/Icons.jsx'

export function SelectedRouteDetails({ selectedRoute }) {
  if (!selectedRoute) {
    return (
      <Card className="w-full">
        <CardHeader>
          <div>
            <CardTitle>Selected Route Details</CardTitle>
            <CardDescription>
              Stop schedules, transit sequence, and ETA telemetry
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-8 text-center text-xs sm:text-sm text-slate-500 space-y-1">
          <p className="text-slate-400 font-medium">Select a route</p>
          <p className="text-slate-500 max-w-sm mx-auto leading-relaxed">
            Choose an active vehicle route from the list above to inspect its stop schedule and transit sequence.
          </p>
        </CardContent>
      </Card>
    )
  }

  const visitOrder = selectedRoute.visit_order || []
  const nodeSequence = selectedRoute.node_sequence || []
  const distance = Number(selectedRoute.total_distance || 0).toFixed(1)
  const travelTime = Number(selectedRoute.total_travel_time || 0).toFixed(1)
  const eta = selectedRoute.estimated_arrival != null
    ? `${Number(selectedRoute.estimated_arrival).toFixed(1)} min remaining`
    : 'Not available'
  const isAffected = selectedRoute.status === 'AFFECTED'

  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <FleetIcon className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <CardTitle>Vehicle #{selectedRoute.vehicle_id} Schedule</CardTitle>
              <Badge variant={isAffected ? 'warning' : 'success'} size="sm" dot>
                {isAffected ? 'AFFECTED' : 'ACTIVE'}
              </Badge>
            </div>
            <CardDescription>
              Dispatch Depot #{selectedRoute.depot_node} · {visitOrder.length} customer dropoffs
            </CardDescription>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-mono">
            Depot #{selectedRoute.depot_node}
          </span>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-5 sm:p-6 space-y-6">
        {/* Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-medium">Route Distance</span>
            <div className="text-lg font-bold font-mono text-slate-200">{distance} km</div>
            <span className="text-[11px] text-slate-500">Cumulative spatial length</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-medium">Travel Time</span>
            <div className="text-lg font-bold font-mono text-blue-400">{travelTime} min</div>
            <span className="text-[11px] text-slate-500">Estimated duration</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-medium">Estimated Arrival</span>
            <div className="text-lg font-bold font-mono text-emerald-400">{eta}</div>
            <span className="text-[11px] text-slate-500">Real-time arrival projection</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
            <span className="text-xs text-slate-500 font-medium">Delivery Stops</span>
            <div className="text-lg font-bold font-mono text-purple-400">{visitOrder.length} Stops</div>
            <span className="text-[11px] text-slate-500">Customer dropoff waypoints</span>
          </div>
        </div>

        {/* Visit Order Sequence Timeline */}
        <div className="space-y-2.5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Customer Delivery Visit Order
          </h4>

          <div className="flex flex-wrap items-center gap-2 p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl overflow-x-auto">
            {/* Start Depot */}
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-950/80 border border-amber-800/80 text-amber-300 font-mono text-xs font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              DEPOT #{selectedRoute.depot_node} (Origin)
            </span>

            {visitOrder.map((custId, idx) => (
              <div key={`stop-${idx}`} className="flex items-center gap-2">
                <span className="text-slate-600 font-bold text-xs">→</span>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 font-mono text-xs font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Stop #{idx + 1}: Customer #{custId}
                </span>
              </div>
            ))}

            {/* Return Depot */}
            <span className="text-slate-600 font-bold text-xs">→</span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-950/80 border border-amber-800/80 text-amber-300 font-mono text-xs font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              DEPOT #{selectedRoute.depot_node} (Return)
            </span>
          </div>
        </div>

        {/* Full Node Transit Sequence */}
        <div className="space-y-2.5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
            Full Technical Node Sequence ({nodeSequence.length} Topological Steps)
          </h4>

          <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl font-mono text-xs text-slate-300 overflow-x-auto leading-relaxed">
            {nodeSequence.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5">
                {nodeSequence.map((nodeId, idx) => (
                  <span key={`node-seq-${idx}`} className="inline-flex items-center gap-1.5">
                    <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200">
                      N{nodeId}
                    </span>
                    {idx < nodeSequence.length - 1 && (
                      <span className="text-slate-600 font-bold">→</span>
                    )}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-slate-500">No node sequence path recorded.</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default SelectedRouteDetails
