export function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className = '',
}) {
  const variants = {
    neutral: 'bg-slate-800/80 text-slate-300 border-slate-700/80',
    success: 'bg-emerald-950/70 text-emerald-300 border-emerald-800/70',
    warning: 'bg-amber-950/70 text-amber-300 border-amber-800/70',
    error: 'bg-rose-950/70 text-rose-300 border-rose-800/70',
    danger: 'bg-rose-950/70 text-rose-300 border-rose-800/70',
    info: 'bg-blue-950/70 text-blue-300 border-blue-800/70',
  }

  const dotColors = {
    neutral: 'bg-slate-400',
    success: 'bg-emerald-400',
    warning: 'bg-amber-400',
    error: 'bg-rose-400',
    danger: 'bg-rose-400',
    info: 'bg-blue-400',
  }

  const sizes = {
    sm: 'px-2 py-0.5 text-[11px] font-mono',
    md: 'px-2.5 py-0.5 text-xs',
    lg: 'px-3 py-1 text-sm',
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-full shrink-0 select-none ${
        variants[variant] || variants.neutral
      } ${sizes[size] || sizes.md} ${className}`}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            dotColors[variant] || dotColors.neutral
          }`}
        />
      )}
      <span>{children}</span>
    </span>
  )
}

export default Badge
