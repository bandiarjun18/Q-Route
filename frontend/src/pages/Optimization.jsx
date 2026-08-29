import { useState } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { OptimizationConfigForm } from '../components/optimization/OptimizationConfigForm.jsx'
import { OptimizationSummaryCards } from '../components/optimization/OptimizationSummaryCards.jsx'
import { OptimizationResultCard } from '../components/optimization/OptimizationResultCard.jsx'
import { runOptimization } from '../api/qroute.js'

const DEFAULT_OPTIMIZE_PARAMS = {
  n_particles: 20,
  max_iterations: 100,
  time_budget_seconds: '',
  seed: 42,
  w_time: 1.0,
  w_distance: 0.5,
  w_congestion: 0.3,
}

export function Optimization() {
  const [params, setParams] = useState(DEFAULT_OPTIMIZE_PARAMS)
  const [result, setResult] = useState(null)
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
    setParams(DEFAULT_OPTIMIZE_PARAMS)
    if (error) setError(null)
  }

  const handleRunOptimization = async () => {
    // Client-side validation matching backend schema
    if (Number(params.n_particles) < 2) {
      setError('Particles must be at least 2.')
      return
    }
    if (Number(params.max_iterations) < 1) {
      setError('Max iterations must be at least 1.')
      return
    }
    if (Number(params.w_time) <= 0 || Number(params.w_distance) <= 0) {
      setError('Time and distance weights must be greater than 0.')
      return
    }
    if (Number(params.w_congestion) < 0) {
      setError('Congestion weight must be non-negative (≥ 0).')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const data = await runOptimization(params)
      setResult(data)
    } catch (err) {
      setError(
        err?.message ||
          'Failed to execute optimization. Ensure both the network (POST /network) and fleet (POST /fleet) have been configured first.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header */}
      <PageHeader
        title="Optimization"
        subtitle="Configure and execute QPSO route optimization for the current fleet."
      />

      {/* 2. Optimization Configuration Card */}
      <OptimizationConfigForm
        params={params}
        onChangeParam={handleParamChange}
        onApplyPreset={handleApplyPreset}
        onRunOptimization={handleRunOptimization}
        onResetDefaults={handleResetDefaults}
        isLoading={isLoading}
        error={error}
      />

      {/* 3. Optimization Summary Cards (4 Columns) */}
      <OptimizationSummaryCards result={result} />

      {/* 4. Optimization Result & Telemetry Card */}
      <OptimizationResultCard
        result={result}
        isLoading={isLoading}
        onRunOptimization={handleRunOptimization}
      />
    </div>
  )
}

export default Optimization
