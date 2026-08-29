import { Card, CardContent } from '../ui/Card.jsx'

export function StatCard({
  title,
  value,
  subtitle,
  icon = null,
  badge = null,
  accentColor = 'blue',
  valueColor = 'text-slate-100',
  className = '',
}) {
  const accentBorderClasses = {
    blue: 'hover:border-blue-500/40',
    green: 'hover:border-emerald-500/40',
    purple: 'hover:border-indigo-500/40',
    amber: 'hover:border-amber-500/40',
  }

  const iconClasses = {
    blue: 'bg-blue-950/70 border-blue-800/60 text-blue-400',
    green: 'bg-emerald-950/70 border-emerald-800/60 text-emerald-400',
    purple: 'bg-indigo-950/70 border-indigo-800/60 text-indigo-400',
    amber: 'bg-amber-950/70 border-amber-800/60 text-amber-400',
  }

  return (
    <Card className={`h-full min-h-[128px] transition-all duration-150 ${accentBorderClasses[accentColor] || ''} ${className}`}>
      <CardContent className="p-5 sm:p-6 flex flex-col justify-between h-full space-y-4">
        {/* Top: Label on left, Icon on right */}
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs sm:text-sm font-medium text-slate-400 truncate tracking-wide">
            {title}
          </span>
          {icon && (
            <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 ${iconClasses[accentColor] || 'bg-slate-900 border-slate-800 text-slate-400'}`}>
              {icon}
            </div>
          )}
        </div>

        {/* Bottom: Large value and supporting text */}
        <div className="space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <div className={`text-2xl sm:text-3xl font-bold font-mono tracking-tight leading-none ${valueColor}`}>
              {value}
            </div>
            {badge && <div className="shrink-0">{badge}</div>}
          </div>

          {subtitle && (
            <p className="text-xs text-slate-500 truncate leading-normal pt-0.5">
              {subtitle}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default StatCard
