import { useState, useEffect } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { FleetSummaryCards } from '../components/fleet/FleetSummaryCards.jsx'
import { FleetConfigCard } from '../components/fleet/FleetConfigCard.jsx'
import { VehiclesTableCard } from '../components/fleet/VehiclesTableCard.jsx'
import { CustomerOrdersTableCard } from '../components/fleet/CustomerOrdersTableCard.jsx'
import { AddVehicleModal } from '../components/fleet/AddVehicleModal.jsx'
import { AddCustomerModal } from '../components/fleet/AddCustomerModal.jsx'
import { configureFleet, getNetwork, getCurrentFleet } from '../api/qroute.js'

const SYNTHETIC_VEHICLES = [
  { vehicle_id: 0, capacity: 50.0, depot_node: 0 },
  { vehicle_id: 1, capacity: 50.0, depot_node: 0 },
]

const SYNTHETIC_CUSTOMERS = [
  { customer_id: 0, location_node: 3, demand: 8.5 },
  { customer_id: 1, location_node: 7, demand: 6.0 },
  { customer_id: 2, location_node: 11, demand: 4.2 },
]

const OSM_VEHICLES = [
  { vehicle_id: 0, capacity: 50.0, depot_node: 1001 },
  { vehicle_id: 1, capacity: 45.0, depot_node: 1001 },
]

const OSM_CUSTOMERS = [
  { customer_id: 0, location_node: 1002, demand: 12.0 },
  { customer_id: 1, location_node: 1003, demand: 10.0 },
  { customer_id: 2, location_node: 1004, demand: 14.0 },
  { customer_id: 3, location_node: 1005, demand: 8.0 },
  { customer_id: 4, location_node: 1006, demand: 11.0 },
  { customer_id: 5, location_node: 1007, demand: 9.0 },
]

export function Fleet() {
  const [vehicles, setVehicles] = useState(SYNTHETIC_VEHICLES)
  const [customers, setCustomers] = useState(SYNTHETIC_CUSTOMERS)
  const [isGeographic, setIsGeographic] = useState(false)
  const [isAddVehicleOpen, setIsAddVehicleOpen] = useState(false)
  const [isAddCustomerOpen, setIsAddCustomerOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  useEffect(() => {
    let isMounted = true

    async function initFleet() {
      try {
        const net = await getNetwork()
        if (!isMounted || !net?.nodes?.length) return

        const isGeo = net.nodes.some(
          (n) => n.lat != null && n.lon != null
        )
        setIsGeographic(isGeo)

        try {
          const activeFleet = await getCurrentFleet()
          if (!isMounted) return
          if (activeFleet?.vehicles?.length > 0) {
            setVehicles(activeFleet.vehicles)
            setCustomers(activeFleet.customers)
            return
          }
        } catch {
          // No active fleet configured yet in backend
        }

        if (isGeo) {
          setVehicles(OSM_VEHICLES)
          setCustomers(OSM_CUSTOMERS)
        } else {
          setVehicles(SYNTHETIC_VEHICLES)
          setCustomers(SYNTHETIC_CUSTOMERS)
        }
      } catch {
        // Backend not running or no network loaded yet
      }
    }

    initFleet()
    return () => {
      isMounted = false
    }
  }, [])

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
          vehicle_id: isNaN(Number(v.vehicle_id)) ? String(v.vehicle_id) : Number(v.vehicle_id),
          capacity: Number(v.capacity),
          depot_node: isNaN(Number(v.depot_node)) ? String(v.depot_node) : Number(v.depot_node),
        })),
        customers: customers.map((c) => ({
          customer_id: isNaN(Number(c.customer_id)) ? String(c.customer_id) : Number(c.customer_id),
          location_node: isNaN(Number(c.location_node)) ? String(c.location_node) : Number(c.location_node),
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
        isGeographic={isGeographic}
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
        defaultNextId={vehicles.length > 0 ? Math.max(...vehicles.map((v) => (isNaN(Number(v.vehicle_id)) ? 0 : Number(v.vehicle_id)))) + 1 : 0}
        defaultDepotNode={isGeographic ? 1001 : 0}
      />

      {/* Add Customer Modal */}
      <AddCustomerModal
        isOpen={isAddCustomerOpen}
        onClose={() => setIsAddCustomerOpen(false)}
        onAdd={handleAddCustomer}
        defaultNextId={customers.length > 0 ? Math.max(...customers.map((c) => (isNaN(Number(c.customer_id)) ? 0 : Number(c.customer_id)))) + 1 : 0}
        defaultLocationNode={isGeographic ? 1002 : 1}
      />
    </div>
  )
}

export default Fleet
