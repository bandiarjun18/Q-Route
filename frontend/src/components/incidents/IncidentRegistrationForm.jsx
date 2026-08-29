import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Input } from '../ui/Input.jsx'
import { Select } from '../ui/Select.jsx'
import { IncidentsIcon, RefreshIcon } from '../common/Icons.jsx'
import { networkPreviewData } from '../../data/dashboardData.js'

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
  isLoading,
  error,
}) {
  // Extract available edges from network preview data
  const availableEdges = networkPreviewData?.edges || [
    { u: 3, v: 7 },
    { u: 0, v: 1 },
    { u: 1, v: 2 },
    { u: 2, v: 5 },
    { u: 5, v: 8 },
  ]

  const [selectedEdgeKey, setSelectedEdgeKey] = useState(
    availableEdges.length > 0 ? `${availableEdges[0].u}-${availableEdges[0].v}` : '3-7'
  )
  const [incidentType, setIncidentType] = useState('ACCIDENT')
  const [severity, setSeverity] = useState('MEDIUM')
  const [description, setDescription] = useState('Multi-vehicle collision on primary corridor')

  const handleSubmit = (e) => {
    e.preventDefault()
    const [uStr, vStr] = selectedEdgeKey.split('-')
    const edge_u = Number(uStr)
    const edge_v = Number(vStr)

    onSubmitIncident({
      edge_u,
      edge_v,
      incident_type: incidentType,
      severity,
      description,
    })
  }

  const handleSimulatePreset = (type, sev, u, v, desc) => {
    setSelectedEdgeKey(`${u}-${v}`)
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
                3,
                7,
                'Emergency road closure due to water main breach'
              )
            }
            className="text-xs h-7.5 px-2.5 text-slate-400 hover:text-slate-200 border border-slate-800 bg-slate-900/50"
            disabled={isLoading}
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
                0,
                1,
                'Severe multi-car crash blocking main outbound lane'
              )
            }
            className="text-xs h-7.5 px-2.5 text-slate-400 hover:text-slate-200 border border-slate-800 bg-slate-900/50"
            disabled={isLoading}
          >
            Crash Preset
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-5 sm:p-6 space-y-5">
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
              value={selectedEdgeKey}
              onChange={(e) => setSelectedEdgeKey(e.target.value)}
              disabled={isLoading}
              required
            >
              {availableEdges.map((edge, idx) => (
                <option key={`edge-opt-${idx}`} value={`${edge.u}-${edge.v}`}>
                  Edge: Node N{edge.u} → Node N{edge.v}
                </option>
              ))}
            </Select>

            <Select
              label="Incident Category"
              value={incidentType}
              onChange={(e) => setIncidentType(e.target.value)}
              options={INCIDENT_TYPES}
              disabled={isLoading}
              required
            />

            <Select
              label="Severity & Delay Factor"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              options={SEVERITIES}
              disabled={isLoading}
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
              disabled={isLoading}
            />

            <div className="flex items-center gap-2 pb-0.5">
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isLoading}
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
                }}
                disabled={isLoading}
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
