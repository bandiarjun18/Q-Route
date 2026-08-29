export function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  leftIcon = null,
  rightIcon = null,
  className = '',
  type = 'button',
  onClick,
  ...props
}) {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-lg transition-colors duration-150 cursor-pointer select-none disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950'

  const variants = {
    primary:
      'bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white shadow-xs focus:ring-blue-500/80 border border-blue-500/30',
    secondary:
      'bg-slate-800 hover:bg-slate-700 active:bg-slate-900 text-slate-200 hover:text-white border border-slate-700 shadow-xs focus:ring-slate-500',
    outline:
      'bg-transparent hover:bg-slate-800 active:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 focus:ring-slate-500',
    ghost:
      'bg-transparent hover:bg-slate-800 text-slate-400 hover:text-slate-100 focus:ring-slate-500',
    danger:
      'bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white shadow-xs focus:ring-rose-500/80 border border-rose-500/30',
  }

  const sizes = {
    sm: 'h-8 px-3 text-xs gap-1.5',
    md: 'h-10 px-4 text-sm gap-2',
    lg: 'h-11 px-5 text-base gap-2.5',
  }

  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      onClick={onClick}
      className={`${baseStyles} ${variants[variant] || variants.primary} ${
        sizes[size] || sizes.md
      } ${className}`}
      {...props}
    >
      {isLoading ? (
        <>
          <span className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin shrink-0" />
          <span>{children}</span>
        </>
      ) : (
        <>
          {leftIcon && <span className="shrink-0">{leftIcon}</span>}
          <span>{children}</span>
          {rightIcon && <span className="shrink-0">{rightIcon}</span>}
        </>
      )}
    </button>
  )
}

export default Button
