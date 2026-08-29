import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../ui/Table.jsx'
import { PlusIcon, TrashIcon, UsersIcon, MapPinIcon } from '../common/Icons.jsx'

export function CustomerOrdersTableCard({ customers = [], onOpenAddCustomer, onDeleteCustomer }) {
  return (
    <Card className="w-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Customer Delivery Orders</CardTitle>
          <CardDescription>
            Delivery demand configured for route optimization
          </CardDescription>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="neutral" size="sm">
            {customers.length} Orders
          </Badge>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            leftIcon={<PlusIcon className="w-3.5 h-3.5" />}
            onClick={onOpenAddCustomer}
            className="h-8 px-3 text-xs"
          >
            Add Order
          </Button>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-0">
        {customers.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order ID</TableHead>
                <TableHead>Delivery Node</TableHead>
                <TableHead>Cargo Demand</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Order Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {customers.map((c, idx) => (
                <TableRow key={c.customer_id ?? idx}>
                  <TableCell className="font-semibold text-slate-100 font-mono">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-md bg-emerald-950/80 border border-emerald-800/60 flex items-center justify-center text-emerald-400 text-xs">
                        <UsersIcon className="w-3 h-3" />
                      </div>
                      <span>ORDER #{c.customer_id}</span>
                    </div>
                  </TableCell>

                  <TableCell className="font-mono text-slate-300">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 text-emerald-300 border border-slate-700 text-xs">
                      <MapPinIcon className="w-3 h-3 text-emerald-400" />
                      NODE #{c.location_node}
                    </span>
                  </TableCell>

                  <TableCell className="font-mono text-slate-200">
                    <span className="font-bold text-slate-100">{Number(c.demand).toFixed(1)}</span> units
                  </TableCell>

                  <TableCell>
                    <span className="text-xs font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
                      Standard
                    </span>
                  </TableCell>

                  <TableCell>
                    <Badge variant="warning" size="sm" dot>
                      PENDING
                    </Badge>
                  </TableCell>

                  <TableCell className="text-right">
                    <button
                      type="button"
                      onClick={() => onDeleteCustomer(c.customer_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                      title={`Remove Order #${c.customer_id}`}
                      aria-label={`Remove Order #${c.customer_id}`}
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
            <div className="w-10 h-10 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-emerald-400">
              <UsersIcon className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-slate-200">No customer orders configured</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto leading-normal">
                Add customer delivery locations and payload demands to prepare the fleet for route optimization.
              </p>
            </div>
            <Button variant="primary" size="sm" onClick={onOpenAddCustomer} leftIcon={<PlusIcon className="w-3.5 h-3.5" />}>
              Add Customer Order
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default CustomerOrdersTableCard
