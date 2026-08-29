import { useState } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { NetworkConfigForm } from '../components/network/NetworkConfigForm.jsx'
import { NetworkStatsCards } from '../components/network/NetworkStatsCards.jsx'
import { NetworkCanvas } from '../components/network/NetworkCanvas.jsx'
import { NetworkLegend } from '../components/network/NetworkLegend.jsx'
import { createNetwork } from '../api/qroute.js'

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

    try {
      const data = await createNetwork(params)
      setNetworkData(data)
    } catch (err) {
      setError(err?.message || 'Failed to generate network from backend API. Please ensure the server is running on port 8000.')
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
      />

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
