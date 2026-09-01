import { useState, useEffect } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { IncidentRegistrationForm } from '../components/incidents/IncidentRegistrationForm.jsx'
import { IncidentImpactSummary } from '../components/incidents/IncidentImpactSummary.jsx'
import { AffectedRoutesTable } from '../components/incidents/AffectedRoutesTable.jsx'
import { IncidentDetailsCard } from '../components/incidents/IncidentDetailsCard.jsx'
import { registerIncident, getNetwork, getCurrentIncident } from '../api/qroute.js'

export function Incidents() {
  const [incidentResult, setIncidentResult] = useState(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState(null)
  const [availableEdges, setAvailableEdges] = useState([])
  const [isNetworkLoading, setIsNetworkLoading] = useState(false)
  const [networkError, setNetworkError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let isMounted = true

    async function initIncidentPage() {
      setIsNetworkLoading(true)
      setNetworkError(null)

      try {
        const net = await getNetwork()
        if (!isMounted) return
        if (net?.edges && net.edges.length > 0) {
          setAvailableEdges(net.edges)
        } else {
          setAvailableEdges([])
        }
      } catch (err) {
        if (!isMounted) return
        setNetworkError(err?.message || 'Failed to fetch current network topology.')
      } finally {
        if (isMounted) {
          setIsNetworkLoading(false)
        }
      }

      try {
        const activeInc = await getCurrentIncident()
        if (!isMounted) return
        if (activeInc) {
          setIncidentResult(activeInc)
          if (activeInc?.updated_routes?.length > 0) {
            setSelectedVehicleId(activeInc.updated_routes[0].vehicle_id)
          }
        }
      } catch {
        // No incident registered yet
      }
    }

    initIncidentPage()
    return () => {
      isMounted = false
    }
  }, [])

  const handleRegisterIncident = async (payload) => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await registerIncident(payload)
      setIncidentResult(data)
      if (data?.updated_routes?.length > 0) {
        setSelectedVehicleId(data.updated_routes[0].vehicle_id)
      } else {
        setSelectedVehicleId(null)
      }
    } catch (err) {
      setError(
        err?.message ||
          'Failed to register road incident. Ensure optimization (POST /optimize) has been executed first.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const updatedRoutes = incidentResult?.updated_routes || []
  const selectedRoute = updatedRoutes.find((r) => r.vehicle_id === selectedVehicleId)

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header */}
      <PageHeader
        title="Incidents"
        subtitle="Register road incidents and monitor their impact on active routes."
      />

      {/* 2. Incident Registration Card */}
      <IncidentRegistrationForm
        onSubmitIncident={handleRegisterIncident}
        availableEdges={availableEdges}
        isNetworkLoading={isNetworkLoading}
        networkError={networkError}
        isLoading={isLoading}
        error={error}
      />

      {/* 3. Incident Impact Summary (4 Columns) */}
      <IncidentImpactSummary incidentResult={incidentResult} />

      {/* 4. Affected & Re-Optimized Routes Table */}
      <AffectedRoutesTable
        incidentResult={incidentResult}
        updatedRoutes={updatedRoutes}
        selectedVehicleId={selectedVehicleId}
        onSelectRoute={setSelectedVehicleId}
      />

      {/* 5. Incident Details & Route Sequence Inspection */}
      <IncidentDetailsCard
        incidentResult={incidentResult}
        selectedRoute={selectedRoute}
      />
    </div>
  )
}

export default Incidents
