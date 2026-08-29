export function Card({ children, className = '', ...props }) {
  return (
    <div
      className={`bg-slate-900/90 border border-slate-800 rounded-xl shadow-xs overflow-hidden ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '', ...props }) {
  return (
    <div
      className={`px-5 sm:px-6 py-4 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardTitle({ children, className = '', ...props }) {
  return (
    <h3
      className={`text-base sm:text-lg font-semibold text-slate-100 tracking-tight leading-snug ${className}`}
      {...props}
    >
      {children}
    </h3>
  )
}

export function CardDescription({ children, className = '', ...props }) {
  return (
    <p className={`text-xs sm:text-sm text-slate-400 mt-0.5 leading-normal ${className}`} {...props}>
      {children}
    </p>
  )
}

export function CardContent({ children, className = '', ...props }) {
  return (
    <div className={`p-5 sm:p-6 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({ children, className = '', ...props }) {
  return (
    <div
      className={`px-5 sm:px-6 py-3.5 border-t border-slate-800/80 flex items-center justify-between gap-3 bg-slate-950/40 text-xs sm:text-sm text-slate-400 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export default Card
