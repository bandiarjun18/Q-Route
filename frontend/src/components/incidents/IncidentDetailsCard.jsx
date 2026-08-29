import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Badge } from '../ui/Badge.jsx'
import { FleetIcon, IncidentsIcon } from '../common/Icons.jsx'

export function IncidentDetailsCard({ incidentResult, selectedRoute }) {
  if (!incidentResult) {
    return null
  }

  const isClosure = Boolean(incidentResult.is_closure)
  const visitOrder = selectedRoute?.visit_order || []
  const nodeSequence = selectedRoute?.node_sequence || []

  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-rose-600/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
            <IncidentsIcon className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <CardTitle>
                Incident: Corridor N{incidentResult.edge_u} → N{incidentResult.edge_v}
              </CardTitle>
              <Badge variant={isClosure ? 'danger' : 'warning'} size="sm" dot>
                {isClosure ? 'ROAD CLOSED' : 'ROAD IMPACTED'}
              </Badge>
            </div>
            <CardDescription>
              Category: {incidentResult.incident_type} · Severity: {incidentResult.severity}
            </CardDescription>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-slate-400">
          <span>Impacted Edge: ({incidentResult.edge_u}, {incidentResult.edge_v})</span>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-5 sm:p-6 space-y-6">
        {/* Incident Summary Banner */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2 text-xs sm:text-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 text-slate-300">
            <div>
              <span className="font-semibold text-slate-100">Disruption Note:</span>{' '}
              <span className="text-slate-300">
                {incidentResult.description || 'No additional incident notes provided.'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-500 font-mono">
                Affected Fleet Units: {incidentResult.n_affected}
              </span>
              <span className="text-slate-600">·</span>
              <span className="text-slate-500 font-mono">
                Unaffected Routes: {incidentResult.unaffected_route_count}
              </span>
            </div>
          </div>
        </div>

        {/* Selected Route Inspection Details */}
        {selectedRoute ? (
          <div className="space-y-4 pt-2 border-t border-slate-800/80">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <FleetIcon className="w-4 h-4 text-blue-400" />
                Selected Re-Optimized Itinerary (Vehicle #{selectedRoute.vehicle_id})
              </h4>
              <div className="text-xs text-slate-400 font-mono">
                Distance: {Number(selectedRoute.total_distance).toFixed(1)} km · Duration: {Number(selectedRoute.total_travel_time).toFixed(1)} min
              </div>
            </div>

            {/* Visit Order Sequence */}
            <div className="space-y-2">
              <span className="text-xs text-slate-400 font-medium">Customer Dropoff Sequence</span>
              <div className="flex flex-wrap items-center gap-2 p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl overflow-x-auto">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-950/80 border border-amber-800/80 text-amber-300 font-mono text-xs font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  DEPOT #{selectedRoute.depot_node} (Origin)
                </span>

                {visitOrder.map((custId, idx) => (
                  <div key={`reopt-stop-${idx}`} className="flex items-center gap-2">
                    <span className="text-slate-600 font-bold text-xs">→</span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 font-mono text-xs font-semibold">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Stop #{idx + 1}: Customer #{custId}
                    </span>
                  </div>
                ))}

                <span className="text-slate-600 font-bold text-xs">→</span>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-950/80 border border-amber-800/80 text-amber-300 font-mono text-xs font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  DEPOT #{selectedRoute.depot_node} (Return)
                </span>
              </div>
            </div>

            {/* Node Sequence */}
            <div className="space-y-2">
              <span className="text-xs text-slate-400 font-medium">Topological Transit Sequence</span>
              <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl font-mono text-xs text-slate-300 overflow-x-auto leading-relaxed">
                {nodeSequence.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {nodeSequence.map((nodeId, idx) => (
                      <span key={`reopt-seq-${idx}`} className="inline-flex items-center gap-1.5">
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
                  <span className="text-slate-500">No transit sequence available.</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center text-xs text-slate-500">
            Select a re-optimized vehicle route from the table above to inspect its updated delivery waypoints and transit sequence.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default IncidentDetailsCard
