export function PageHeader({ title, subtitle, actions = null, className = '' }) {
  return (
    <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800/80 w-full ${className}`}>
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-100 leading-snug">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm sm:text-base text-slate-400 mt-1 leading-normal max-w-3xl">
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
    </div>
  )
}

export default PageHeader
