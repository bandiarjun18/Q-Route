import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Input } from '../ui/Input.jsx'

export function AddVehicleModal({ isOpen, onClose, onAdd, defaultNextId = 0 }) {
  const [vehicleId, setVehicleId] = useState(defaultNextId)
  const [capacity, setCapacity] = useState('50.0')
  const [depotNode, setDepotNode] = useState('0')
  const [error, setError] = useState(null)

  if (!isOpen) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    const capNum = Number(capacity)
    const depotNum = Number(depotNode)
    const idNum = Number(vehicleId)

    if (isNaN(capNum) || capNum <= 0) {
      setError('Capacity must be a positive number greater than 0.')
      return
    }
    if (isNaN(depotNum) || depotNum < 0) {
      setError('Depot Node must be a valid non-negative integer.')
      return
    }

    onAdd({
      vehicle_id: isNaN(idNum) ? defaultNextId : idNum,
      capacity: capNum,
      depot_node: depotNum,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
      <div className="w-full max-w-md">
        <Card className="shadow-2xl border-slate-700 bg-slate-900">
          <CardHeader className="py-4">
            <CardTitle className="text-base">Add Vehicle to Fleet</CardTitle>
            <button
              type="button"
              onClick={onClose}
              className="text-slate-400 hover:text-slate-100 p-1 cursor-pointer transition-colors"
              aria-label="Close modal"
            >
              ✕
            </button>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="p-5 space-y-4">
              {error && (
                <div className="p-2.5 bg-rose-950/80 border border-rose-800 rounded-lg text-rose-300 text-xs">
                  {error}
                </div>
              )}

              <Input
                label="Vehicle ID"
                type="number"
                min="0"
                value={vehicleId}
                onChange={(e) => setVehicleId(e.target.value)}
                helperText="Unique numerical identifier"
                required
              />

              <Input
                label="Payload Capacity (units)"
                type="number"
                step="0.5"
                min="0.1"
                value={capacity}
                onChange={(e) => {
                  setCapacity(e.target.value)
                  if (error) setError(null)
                }}
                helperText="Maximum cargo payload limit (> 0)"
                required
              />

              <Input
                label="Home Depot Node ID"
                type="number"
                min="0"
                value={depotNode}
                onChange={(e) => {
                  setDepotNode(e.target.value)
                  if (error) setError(null)
                }}
                helperText="Dispatch depot node in the network"
                required
              />
            </CardContent>

            <CardFooter className="py-3 px-5 justify-end gap-2.5">
              <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Add Vehicle
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  )
}

export default AddVehicleModal
