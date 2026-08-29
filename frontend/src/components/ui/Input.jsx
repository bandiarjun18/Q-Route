export function Input({
  label,
  helperText,
  error,
  id,
  type = 'text',
  className = '',
  required = false,
  ...props
}) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-xs sm:text-sm font-medium text-slate-300 select-none">
          {label} {required && <span className="text-rose-400">*</span>}
        </label>
      )}
      <input
        id={inputId}
        type={type}
        required={required}
        className={`w-full h-10 bg-slate-950/90 border ${
          error
            ? 'border-rose-500/80 focus:ring-rose-500/40'
            : 'border-slate-800 focus:border-blue-500 focus:ring-blue-500/30'
        } rounded-lg px-3.5 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-rose-400 font-mono mt-1">{error}</p>}
      {helperText && !error && <p className="text-xs text-slate-500 mt-1">{helperText}</p>}
    </div>
  )
}

export default Input
