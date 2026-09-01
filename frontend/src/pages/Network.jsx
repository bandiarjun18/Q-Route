import { useState, useEffect } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { Button } from '../components/ui/Button.jsx'
import { NetworkConfigForm } from '../components/network/NetworkConfigForm.jsx'
import { NetworkStatsCards } from '../components/network/NetworkStatsCards.jsx'
import { NetworkCanvas } from '../components/network/NetworkCanvas.jsx'
import { NetworkLegend } from '../components/network/NetworkLegend.jsx'
import { MapPinIcon, CheckCircleIcon } from '../components/common/Icons.jsx'
import { createNetwork, loadOSMPresetNetwork, getNetwork } from '../api/qroute.js'

const DEFAULT_PARAMS = {
  n_nodes: 20,
  n_depots: 1,
  n_customers: 6,
  connect_radius_km: 3.5,
  grid_size_km: 10.0,
  closed_fraction: 0.05,
  seed: 42,
}

export function Network() {
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [networkData, setNetworkData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successInfo, setSuccessInfo] = useState(null)

  useEffect(() => {
    let isMounted = true
    async function loadActiveNetwork() {
      try {
        const data = await getNetwork()
        if (isMounted && data && data.nodes && data.nodes.length > 0) {
          setNetworkData(data)
        }
      } catch {
        // No network loaded yet
      }
    }
    loadActiveNetwork()
    return () => {
      isMounted = false
    }
  }, [])

  const handleParamChange = (field, value) => {
    setParams((prev) => ({
      ...prev,
      [field]: value,
    }))
    if (error) setError(null)
  }

  const handleApplyPreset = (presetParams) => {
    setParams(presetParams)
    if (error) setError(null)
  }

  const handleResetDefaults = () => {
    setParams(DEFAULT_PARAMS)
    if (error) setError(null)
  }

  const handleGenerateNetwork = async () => {
    setIsLoading(true)
    setError(null)
    setSuccessInfo(null)

    try {
      const data = await createNetwork(params)
      setNetworkData(data)
      setSuccessInfo('Synthetic network generated and loaded into state.')
    } catch (err) {
      setError(err?.message || 'Failed to generate network from backend API. Please ensure the server is running on port 8000.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleLoadOSM = async () => {
    setIsLoading(true)
    setError(null)
    setSuccessInfo(null)

    try {
      const data = await loadOSMPresetNetwork('bangalore_urban')
      setNetworkData(data)
      setSuccessInfo('Real-World OpenStreetMap urban road network (Bangalore Central) loaded successfully into PostgreSQL and operational state.')
    } catch (err) {
      setError(err?.message || 'Failed to load real-world OSM network from backend API.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header */}
      <PageHeader
        title="Network"
        subtitle="Generate and inspect the transportation network used for fleet routing."
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={handleLoadOSM}
            isLoading={isLoading}
            leftIcon={<MapPinIcon className="w-3.5 h-3.5" />}
            className="text-xs h-8 px-3 font-semibold"
          >
            Load Real-World OSM Network
          </Button>
        }
      />

      {/* Success Notice */}
      {successInfo && (
        <div className="p-3.5 bg-emerald-950/80 border border-emerald-800/80 rounded-lg text-emerald-300 text-xs sm:text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <CheckCircleIcon className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="truncate">{successInfo}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSuccessInfo(null)}
            className="shrink-0 h-6 text-xs px-2 text-emerald-400 hover:text-emerald-200"
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* 2. Network Configuration Card */}
      <NetworkConfigForm
        params={params}
        onChangeParam={handleParamChange}
        onApplyPreset={handleApplyPreset}
        onGenerate={handleGenerateNetwork}
        onResetDefaults={handleResetDefaults}
        isLoading={isLoading}
        error={error}
      />

      {/* 3. Network Statistics Cards (4 Columns) */}
      <NetworkStatsCards networkData={networkData} />

      {/* 4. Full-Width Network Canvas Map */}
      <NetworkCanvas
        networkData={networkData}
        onGenerate={handleGenerateNetwork}
        isLoading={isLoading}
      />

      {/* 5. Legend & Topology Details */}
      <NetworkLegend networkData={networkData} />
    </div>
  )
}

export default Network
