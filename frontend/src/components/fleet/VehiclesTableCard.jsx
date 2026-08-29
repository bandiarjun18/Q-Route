import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../ui/Table.jsx'
import { PlusIcon, TrashIcon, FleetIcon } from '../common/Icons.jsx'

export function VehiclesTableCard({ vehicles = [], onOpenAddVehicle, onDeleteVehicle }) {
  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Vehicles</CardTitle>
          <CardDescription>
            Configured fleet vehicles and payload capacities
          </CardDescription>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="neutral" size="sm">
            {vehicles.length} Configured
          </Badge>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            leftIcon={<PlusIcon className="w-3.5 h-3.5" />}
            onClick={onOpenAddVehicle}
            className="h-8 px-3 text-xs"
          >
            Add Vehicle
          </Button>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-0">
        {vehicles.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Vehicle ID</TableHead>
                <TableHead>Payload Capacity</TableHead>
                <TableHead>Home Depot Node</TableHead>
                <TableHead>Dispatch Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {vehicles.map((v, idx) => (
                <TableRow key={v.vehicle_id ?? idx}>
                  <TableCell className="font-semibold text-slate-100 font-mono">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-md bg-blue-950/80 border border-blue-800/60 flex items-center justify-center text-blue-400 text-xs">
                        <FleetIcon className="w-3 h-3" />
                      </div>
                      <span>VEHICLE #{v.vehicle_id}</span>
                    </div>
                  </TableCell>

                  <TableCell className="font-mono text-slate-200">
                    <span className="font-bold text-slate-100">{Number(v.capacity).toFixed(1)}</span> units
                  </TableCell>

                  <TableCell className="font-mono text-slate-300">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700 text-xs">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      DEPOT #{v.depot_node}
                    </span>
                  </TableCell>

                  <TableCell>
                    <Badge variant="success" size="sm" dot>
                      AVAILABLE
                    </Badge>
                  </TableCell>

                  <TableCell className="text-right">
                    <button
                      type="button"
                      onClick={() => onDeleteVehicle(v.vehicle_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                      title={`Remove Vehicle #${v.vehicle_id}`}
                      aria-label={`Remove Vehicle #${v.vehicle_id}`}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="p-8 text-center space-y-3 flex flex-col items-center justify-center">
            <div className="w-10 h-10 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-blue-400">
              <FleetIcon className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-slate-200">No vehicles configured</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto leading-normal">
                Add dispatch vehicles with payload capacities to build your fleet before running optimization.
              </p>
            </div>
            <Button variant="primary" size="sm" onClick={onOpenAddVehicle} leftIcon={<PlusIcon className="w-3.5 h-3.5" />}>
              Add Vehicle
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default VehiclesTableCard
