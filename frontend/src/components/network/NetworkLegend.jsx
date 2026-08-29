import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Badge } from '../ui/Badge.jsx'

export function NetworkLegend({ networkData }) {
  const nDepots = networkData?.n_depots ?? 0
  const nCustomers = networkData?.n_customers ?? 0
  const nIntersections = networkData?.n_intersections ?? 0
  const connectRadius = networkData?.connect_radius_km ?? 3.5
  const closedFraction = networkData?.closed_fraction ?? 0.05

  return (
    <Card className="w-full">
      <CardHeader>
        <div>
          <CardTitle>Topology Details &amp; Graph Semantics</CardTitle>
          <CardDescription>
            Graph properties, edge weight metrics, and classification rules for fleet routing
          </CardDescription>
        </div>
        <Badge variant="neutral" size="sm">
          M2 Graph Specification
        </Badge>
      </CardHeader>

      <CardContent className="p-5 sm:p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs sm:text-sm">
          {/* Node Types Description */}
          <div className="space-y-3">
            <h4 className="font-semibold text-slate-200 uppercase tracking-wider text-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              Node Classifications
            </h4>
            <div className="space-y-2 text-slate-400">
              <div className="flex items-start gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                <div>
                  <strong className="text-slate-200">Depot ({nDepots}):</strong> Central dispatch hub where all vehicle routes originate and terminate.
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                <div>
                  <strong className="text-slate-200">Customer ({nCustomers}):</strong> Delivery destination with positive cargo demand to be served.
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-500 mt-1.5 shrink-0" />
                <div>
                  <strong className="text-slate-200">Intersection ({nIntersections}):</strong> Waypoint junction allowing road transit without delivery demand.
                </div>
              </div>
            </div>
          </div>

          {/* Edge Weighting Description */}
          <div className="space-y-3">
            <h4 className="font-semibold text-slate-200 uppercase tracking-wider text-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              Edge Weighting Metrics
            </h4>
            <ul className="space-y-2 text-slate-400 list-disc list-inside">
              <li>
                <strong className="text-slate-200">Euclidean Distance:</strong> Spatial travel length calculated between coordinates.
              </li>
              <li>
                <strong className="text-slate-200">Congestion Multiplier:</strong> Dynamic delay factor applied to travel times (1.0 = free flow).
              </li>
              <li>
                <strong className="text-slate-200">Effective Travel Time:</strong> Primary objective penalty minimized by the QPSO solver.
              </li>
            </ul>
          </div>

          {/* Spatial Constraints */}
          <div className="space-y-3">
            <h4 className="font-semibold text-slate-200 uppercase tracking-wider text-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-indigo-400" />
              Connectivity Parameters
            </h4>
            <div className="space-y-2 text-slate-400">
              <div>
                <strong className="text-slate-200">Proximity Threshold:</strong> Road connections established when distance ≤ <span className="font-mono text-slate-300">{connectRadius} km</span>.
              </div>
              <div>
                <strong className="text-slate-200">Disruption Ratio:</strong> <span className="font-mono text-slate-300">{(closedFraction * 100).toFixed(0)}%</span> of road links marked closed to simulate real-world road closures.
              </div>
              <div className="text-[11px] text-slate-500 pt-1">
                Generated networks guarantee reachability across all active delivery nodes.
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default NetworkLegend
