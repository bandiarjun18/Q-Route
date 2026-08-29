import { Button } from './Button.jsx'

export function EmptyState({
  icon = null,
  title,
  description = null,
  actionLabel = null,
  onAction = null,
  className = '',
}) {
  return (
    <div
      className={`p-8 sm:p-12 text-center rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col items-center justify-center space-y-4 ${className}`}
    >
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-blue-400 shadow-xs">
          {icon}
        </div>
      )}
      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base sm:text-lg font-semibold text-slate-100">{title}</h3>
        {description && (
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">{description}</p>
        )}
      </div>
      {actionLabel && (
        <div className="pt-2">
          {onAction ? (
            <Button variant="primary" size="md" onClick={onAction}>
              {actionLabel}
            </Button>
          ) : (
            <span className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-semibold text-blue-400 bg-blue-950/80 border border-blue-800/60 font-mono select-none">
              {actionLabel}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default EmptyState
