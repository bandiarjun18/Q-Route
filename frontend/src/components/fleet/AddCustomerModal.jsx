import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Input } from '../ui/Input.jsx'

export function AddCustomerModal({ isOpen, onClose, onAdd, defaultNextId = 0 }) {
  const [customerId, setCustomerId] = useState(defaultNextId)
  const [locationNode, setLocationNode] = useState('1')
  const [demand, setDemand] = useState('10.0')
  const [error, setError] = useState(null)

  if (!isOpen) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    const demandNum = Number(demand)
    const nodeNum = Number(locationNode)
    const idNum = Number(customerId)

    if (isNaN(demandNum) || demandNum < 0) {
      setError('Demand must be a non-negative number (≥ 0).')
      return
    }
    if (isNaN(nodeNum) || nodeNum < 0) {
      setError('Location Node must be a valid non-negative integer.')
      return
    }

    onAdd({
      customer_id: isNaN(idNum) ? defaultNextId : idNum,
      location_node: nodeNum,
      demand: demandNum,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
      <div className="w-full max-w-md">
        <Card className="shadow-2xl border-slate-700 bg-slate-900">
          <CardHeader className="py-4">
            <CardTitle className="text-base">Add Customer Delivery Order</CardTitle>
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
                label="Customer / Order ID"
                type="number"
                min="0"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                helperText="Unique numerical identifier"
                required
              />

              <Input
                label="Delivery Location Node ID"
                type="number"
                min="0"
                value={locationNode}
                onChange={(e) => {
                  setLocationNode(e.target.value)
                  if (error) setError(null)
                }}
                helperText="Graph node destination in the network"
                required
              />

              <Input
                label="Cargo Demand (units)"
                type="number"
                step="0.5"
                min="0"
                value={demand}
                onChange={(e) => {
                  setDemand(e.target.value)
                  if (error) setError(null)
                }}
                helperText="Payload requirement to deliver (≥ 0)"
                required
              />
            </CardContent>

            <CardFooter className="py-3 px-5 justify-end gap-2.5">
              <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Add Customer Order
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  )
}

export default AddCustomerModal
