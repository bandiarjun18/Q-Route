export function Select({
  label,
  helperText,
  error,
  id,
  options = [],
  children,
  className = '',
  required = false,
  ...props
}) {
  const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={selectId} className="block text-xs sm:text-sm font-medium text-slate-300 select-none">
          {label} {required && <span className="text-rose-400">*</span>}
        </label>
      )}
      <select
        id={selectId}
        required={required}
        className={`w-full h-10 bg-slate-950/90 border ${
          error
            ? 'border-rose-500/80 focus:ring-rose-500/40'
            : 'border-slate-800 focus:border-blue-500 focus:ring-blue-500/30'
        } rounded-lg px-3.5 text-sm text-slate-100 focus:outline-none focus:ring-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
        {...props}
      >
        {options.length > 0
          ? options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))
          : children}
      </select>
      {error && <p className="text-xs text-rose-400 font-mono mt-1">{error}</p>}
      {helperText && !error && <p className="text-xs text-slate-500 mt-1">{helperText}</p>}
    </div>
  )
}

export default Select
