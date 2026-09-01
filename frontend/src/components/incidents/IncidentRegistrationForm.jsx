import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Input } from '../ui/Input.jsx'
import { Select } from '../ui/Select.jsx'
import { IncidentsIcon, RefreshIcon } from '../common/Icons.jsx'

const INCIDENT_TYPES = [
  { value: 'ACCIDENT', label: 'Accident (Vehicle Collision)' },
  { value: 'ROAD_CLOSURE', label: 'Road Closure (Full Blockage)' },
  { value: 'CONSTRUCTION', label: 'Construction (Work Zone Delay)' },
  { value: 'OBSTRUCTION', label: 'Obstruction (Hazard / Debris)' },
]

const SEVERITIES = [
  { value: 'NONE', label: 'None (×1.0 delay)' },
  { value: 'LOW', label: 'Low (×1.2 delay)' },
  { value: 'MEDIUM', label: 'Medium (×1.5 delay)' },
  { value: 'HIGH', label: 'High (×2.0 delay)' },
  { value: 'CRITICAL', label: 'Critical (×3.0 delay)' },
]

export function IncidentRegistrationForm({
  onSubmitIncident,
  availableEdges = [],
  isNetworkLoading = false,
  networkError = null,
  isLoading,
  error,
}) {
  const [userSelectedEdgeKey, setUserSelectedEdgeKey] = useState('')
  const [incidentType, setIncidentType] = useState('ACCIDENT')
  const [severity, setSeverity] = useState('MEDIUM')
  const [description, setDescription] = useState('Multi-vehicle collision on primary corridor')

  // Derive the active edge key from available edges if no valid user selection exists
  const activeEdgeKey =
    userSelectedEdgeKey && availableEdges.some((e) => `${e.u}__${e.v}` === userSelectedEdgeKey)
      ? userSelectedEdgeKey
      : availableEdges.length > 0
      ? `${availableEdges[0].u}__${availableEdges[0].v}`
      : ''

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!activeEdgeKey) return

    const [uStr, vStr] = activeEdgeKey.split('__')
    const edge_u = isNaN(Number(uStr)) ? uStr : Number(uStr)
    const edge_v = isNaN(Number(vStr)) ? vStr : Number(vStr)

    onSubmitIncident({
      edge_u,
      edge_v,
      incident_type: incidentType,
      severity,
      description,
    })
  }

  const handleSimulatePreset = (type, sev, desc, edgeIndex = 0) => {
    if (availableEdges.length > 0) {
      const idx = edgeIndex < availableEdges.length ? edgeIndex : 0
      const targetEdge = availableEdges[idx]
      setUserSelectedEdgeKey(`${targetEdge.u}__${targetEdge.v}`)
    }
    setIncidentType(type)
    setSeverity(sev)
    setDescription(desc)
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div>
          <CardTitle>Register Incident</CardTitle>
          <CardDescription>
            Record a road incident and trigger dynamic QPSO re-routing for affected fleet vehicles.
          </CardDescription>
        </div>

        {/* Preset Simulators */}
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              handleSimulatePreset(
                'ROAD_CLOSURE',
                'HIGH',
                'Emergency road closure due to water main breach',
                0
              )
            }
            className="text-xs h-7.5 px-2.5 text-slate-400 hover:text-slate-200 border border-slate-800 bg-slate-900/50"
            disabled={isLoading || availableEdges.length === 0}
          >
            Closure Preset
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              handleSimulatePreset(
                'ACCIDENT',
                'CRITICAL',
                'Severe multi-car crash blocking main outbound lane',
                availableEdges.length > 1 ? 1 : 0
              )
            }
            className="text-xs h-7.5 px-2.5 text-slate-400 hover:text-slate-200 border border-slate-800 bg-slate-900/50"
            disabled={isLoading || availableEdges.length === 0}
          >
            Crash Preset
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-5 sm:p-6 space-y-5">
        {/* Network Error or Empty Notice */}
        {networkError && (
          <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm">
            <span className="font-semibold">Network Error: </span>
            {networkError}
          </div>
        )}

        {!isNetworkLoading && availableEdges.length === 0 && !networkError && (
          <div className="p-3.5 bg-amber-950/70 border border-amber-800/70 rounded-lg text-amber-300 text-xs sm:text-sm">
            <span className="font-semibold">No Active Network: </span>
            Please generate or load a transport network before registering road incidents.
          </div>
        )}

        {/* Error Feedback */}
        {error && (
          <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="font-semibold">Incident Registration Failed:</span>
              <span className="truncate">{error}</span>
            </div>
            <Button
              variant="danger"
              size="sm"
              onClick={handleSubmit}
              className="shrink-0 h-7 text-xs px-2.5"
            >
              Try Again
            </Button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Form Row 1: Edge, Type, Severity */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Select
              label="Affected Road Segment (Edge)"
              value={activeEdgeKey}
              onChange={(e) => setUserSelectedEdgeKey(e.target.value)}
              disabled={isLoading || isNetworkLoading || availableEdges.length === 0}
              required
            >
              {availableEdges.length === 0 ? (
                <option value="">
                  {isNetworkLoading ? 'Loading network edges...' : 'No active network edges available'}
                </option>
              ) : (
                availableEdges.map((edge, idx) => (
                  <option key={`edge-opt-${idx}-${edge.u}-${edge.v}`} value={`${edge.u}__${edge.v}`}>
                    Edge: Node {edge.u} → Node {edge.v}
                  </option>
                ))
              )}
            </Select>

            <Select
              label="Incident Category"
              value={incidentType}
              onChange={(e) => setIncidentType(e.target.value)}
              options={INCIDENT_TYPES}
              disabled={isLoading || availableEdges.length === 0}
              required
            />

            <Select
              label="Severity & Delay Factor"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              options={SEVERITIES}
              disabled={isLoading || availableEdges.length === 0}
              required
            />
          </div>

          {/* Form Row 2: Description & Action */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-end">
            <Input
              label="Incident Description (Optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe road blockage or accident details..."
              disabled={isLoading || availableEdges.length === 0}
            />

            <div className="flex items-center gap-2 pb-0.5">
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isLoading}
                disabled={isLoading || availableEdges.length === 0}
                leftIcon={<IncidentsIcon className="w-4 h-4" />}
                className="font-semibold px-5 min-w-[190px]"
              >
                {isLoading ? 'Processing Incident...' : 'Register Incident'}
              </Button>

              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={() => {
                  setDescription('')
                  setIncidentType('ACCIDENT')
                  setSeverity('MEDIUM')
                  if (availableEdges.length > 0) {
                    setUserSelectedEdgeKey(`${availableEdges[0].u}__${availableEdges[0].v}`)
                  }
                }}
                disabled={isLoading || availableEdges.length === 0}
                className="px-3"
                title="Reset form values"
                aria-label="Reset form values"
              >
                <RefreshIcon className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

export default IncidentRegistrationForm
