import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Badge } from '../ui/Badge.jsx'
import { Button } from '../ui/Button.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../ui/Table.jsx'
import { FleetIcon, IncidentsIcon, ArrowRightIcon } from '../common/Icons.jsx'

export function AffectedRoutesTable({
  incidentResult,
  updatedRoutes = [],
  selectedVehicleId,
  onSelectRoute,
}) {
  const hasResult = incidentResult != null

  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Affected Routes</CardTitle>
          <CardDescription>
            Vehicle routes dynamically re-optimized around the incident
          </CardDescription>
        </div>

        {hasResult && (
          <Badge variant={updatedRoutes.length > 0 ? 'warning' : 'success'} size="sm">
            {updatedRoutes.length} Re-Optimized
          </Badge>
        )}
      </CardHeader>

      {/* Content */}
      <CardContent className="p-0">
        {!hasResult ? (
          <div className="p-10 text-center space-y-3 flex flex-col items-center justify-center">
            <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-amber-400">
              <IncidentsIcon className="w-6 h-6" />
            </div>
            <div className="space-y-1 max-w-sm">
              <h4 className="text-base font-semibold text-slate-100">No incidents registered</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Register a road incident above to evaluate affected vehicles and monitor dynamic re-optimization.
              </p>
            </div>
          </div>
        ) : updatedRoutes.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Vehicle</TableHead>
                <TableHead>Depot</TableHead>
                <TableHead>Stops</TableHead>
                <TableHead>Updated Distance</TableHead>
                <TableHead>Updated Travel Time</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Inspection</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {updatedRoutes.map((route) => {
                const isSelected = selectedVehicleId === route.vehicle_id
                const distance = Number(route.total_distance || 0).toFixed(1)
                const travelTime = Number(route.total_travel_time || 0).toFixed(1)
                const nStops = route.visit_order ? route.visit_order.length : 0

                return (
                  <TableRow
                    key={route.vehicle_id}
                    isClickable
                    onClick={() => onSelectRoute(route.vehicle_id)}
                    className={isSelected ? 'bg-blue-950/30 border-blue-500/30' : ''}
                  >
                    <TableCell className="font-semibold text-slate-100 font-mono">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-md bg-amber-950/80 border border-amber-800/60 flex items-center justify-center text-amber-400 text-xs">
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
                      <span className="font-bold text-slate-100">{nStops}</span> customer dropoffs
                    </TableCell>

                    <TableCell className="font-mono text-slate-200">
                      <span className="font-bold text-slate-100">{distance}</span> km
                    </TableCell>

                    <TableCell className="font-mono text-slate-200">
                      <span className="font-bold text-amber-400">{travelTime}</span> min
                    </TableCell>

                    <TableCell>
                      <Badge variant="warning" size="sm" dot>
                        RE-OPTIMIZED
                      </Badge>
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        variant={isSelected ? 'primary' : 'secondary'}
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectRoute(route.vehicle_id)
                        }}
                        rightIcon={<ArrowRightIcon className="w-3 h-3" />}
                        className="text-xs h-7 px-2.5"
                      >
                        {isSelected ? 'Inspecting' : 'Inspect'}
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        ) : (
          <div className="p-8 text-center space-y-2 flex flex-col items-center justify-center">
            <div className="w-8 h-8 rounded-lg bg-emerald-950/80 border border-emerald-800/80 flex items-center justify-center text-emerald-400">
              <IncidentsIcon className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-slate-200">Zero Fleet Routes Affected</h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              The registered incident on corridor N{incidentResult.edge_u} → N{incidentResult.edge_v} does not intersect with any current vehicle transit paths. All fleet itineraries remain nominal.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default AffectedRoutesTable
