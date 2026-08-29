import { useState } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { FleetSummaryCards } from '../components/fleet/FleetSummaryCards.jsx'
import { FleetConfigCard } from '../components/fleet/FleetConfigCard.jsx'
import { VehiclesTableCard } from '../components/fleet/VehiclesTableCard.jsx'
import { CustomerOrdersTableCard } from '../components/fleet/CustomerOrdersTableCard.jsx'
import { AddVehicleModal } from '../components/fleet/AddVehicleModal.jsx'
import { AddCustomerModal } from '../components/fleet/AddCustomerModal.jsx'
import { configureFleet } from '../api/qroute.js'

const INITIAL_VEHICLES = [
  { vehicle_id: 0, capacity: 50.0, depot_node: 0 },
  { vehicle_id: 1, capacity: 50.0, depot_node: 0 },
]

const INITIAL_CUSTOMERS = [
  { customer_id: 0, location_node: 3, demand: 8.5 },
  { customer_id: 1, location_node: 7, demand: 6.0 },
  { customer_id: 2, location_node: 11, demand: 4.2 },
]

export function Fleet() {
  const [vehicles, setVehicles] = useState(INITIAL_VEHICLES)
  const [customers, setCustomers] = useState(INITIAL_CUSTOMERS)
  const [isAddVehicleOpen, setIsAddVehicleOpen] = useState(false)
  const [isAddCustomerOpen, setIsAddCustomerOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  // Handlers for modifying fleet lists
  const handleAddVehicle = (newVeh) => {
    setVehicles((prev) => [...prev, newVeh])
    setSuccessMessage(null)
  }

  const handleDeleteVehicle = (vId) => {
    setVehicles((prev) => prev.filter((v) => v.vehicle_id !== vId))
    setSuccessMessage(null)
  }

  const handleAddCustomer = (newCust) => {
    setCustomers((prev) => [...prev, newCust])
    setSuccessMessage(null)
  }

  const handleDeleteCustomer = (cId) => {
    setCustomers((prev) => prev.filter((c) => c.customer_id !== cId))
    setSuccessMessage(null)
  }

  const handleApplyPreset = (preset) => {
    setVehicles(preset.vehicles)
    setCustomers(preset.customers)
    setError(null)
    setSuccessMessage(null)
  }

  const handleResetFleet = () => {
    setVehicles([])
    setCustomers([])
    setError(null)
    setSuccessMessage(null)
  }

  // Submit fleet configuration to backend POST /fleet
  const handleSubmitFleet = async () => {
    if (vehicles.length === 0 || customers.length === 0) {
      setError('Cannot submit empty fleet: At least 1 vehicle and 1 customer order required.')
      return
    }

    setIsLoading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const payload = {
        vehicles: vehicles.map((v) => ({
          vehicle_id: Number(v.vehicle_id),
          capacity: Number(v.capacity),
          depot_node: Number(v.depot_node),
        })),
        customers: customers.map((c) => ({
          customer_id: Number(c.customer_id),
          location_node: Number(c.location_node),
          demand: Number(c.demand),
        })),
      }

      const res = await configureFleet(payload)
      setSuccessMessage(
        `Fleet configured successfully: ${res.n_vehicles} vehicles and ${res.n_customers} customer orders loaded into optimizer state.`
      )
    } catch (err) {
      setError(
        err?.message ||
          'Failed to configure fleet. Ensure the network has been generated first (POST /network).'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header */}
      <PageHeader
        title="Fleet"
        subtitle="Manage vehicles and customer delivery demand for route optimization."
      />

      {/* 2. Fleet Summary Cards (4 Columns) */}
      <FleetSummaryCards vehicles={vehicles} customers={customers} />

      {/* 3. Fleet Configuration & Presets Toolbar */}
      <FleetConfigCard
        onOpenAddVehicle={() => setIsAddVehicleOpen(true)}
        onOpenAddCustomer={() => setIsAddCustomerOpen(true)}
        onApplyPreset={handleApplyPreset}
        onSubmitFleet={handleSubmitFleet}
        onResetFleet={handleResetFleet}
        isLoading={isLoading}
        error={error}
        successMessage={successMessage}
        vehiclesCount={vehicles.length}
        customersCount={customers.length}
      />

      {/* 4. Vehicles Table Card */}
      <VehiclesTableCard
        vehicles={vehicles}
        onOpenAddVehicle={() => setIsAddVehicleOpen(true)}
        onDeleteVehicle={handleDeleteVehicle}
      />

      {/* 5. Customer Delivery Orders Table Card */}
      <CustomerOrdersTableCard
        customers={customers}
        onOpenAddCustomer={() => setIsAddCustomerOpen(true)}
        onDeleteCustomer={handleDeleteCustomer}
      />

      {/* Add Vehicle Modal */}
      <AddVehicleModal
        isOpen={isAddVehicleOpen}
        onClose={() => setIsAddVehicleOpen(false)}
        onAdd={handleAddVehicle}
        defaultNextId={vehicles.length > 0 ? Math.max(...vehicles.map((v) => v.vehicle_id)) + 1 : 0}
      />

      {/* Add Customer Modal */}
      <AddCustomerModal
        isOpen={isAddCustomerOpen}
        onClose={() => setIsAddCustomerOpen(false)}
        onAdd={handleAddCustomer}
        defaultNextId={customers.length > 0 ? Math.max(...customers.map((c) => c.customer_id)) + 1 : 0}
      />
    </div>
  )
}

export default Fleet
