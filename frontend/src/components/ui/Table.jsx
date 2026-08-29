export function Table({ children, className = '', ...props }) {
  return (
    <div className="w-full overflow-x-auto border border-slate-800 rounded-xl bg-slate-900/60 shadow-xs">
      <table className={`w-full text-left text-sm border-collapse ${className}`} {...props}>
        {children}
      </table>
    </div>
  )
}

export function TableHeader({ children, className = '', ...props }) {
  return (
    <thead
      className={`bg-slate-950/90 text-slate-400 border-b border-slate-800 text-xs uppercase font-semibold tracking-wider ${className}`}
      {...props}
    >
      {children}
    </thead>
  )
}

export function TableBody({ children, className = '', ...props }) {
  return (
    <tbody className={`divide-y divide-slate-800/80 text-slate-200 text-xs sm:text-sm ${className}`} {...props}>
      {children}
    </tbody>
  )
}

export function TableRow({ children, className = '', isClickable = false, ...props }) {
  return (
    <tr
      className={`transition-colors ${
        isClickable ? 'cursor-pointer hover:bg-slate-800/70' : 'hover:bg-slate-800/40'
      } ${className}`}
      {...props}
    >
      {children}
    </tr>
  )
}

export function TableHead({ children, className = '', ...props }) {
  return (
    <th className={`py-3.5 px-4 font-semibold text-slate-400 select-none ${className}`} {...props}>
      {children}
    </th>
  )
}

export function TableCell({ children, className = '', ...props }) {
  return (
    <td className={`py-3.5 px-4 ${className}`} {...props}>
      {children}
    </td>
  )
}

export function TableEmpty({ colSpan, message = 'No data records available.', children }) {
  return (
    <tr>
      <td colSpan={colSpan} className="py-10 px-4 text-center text-slate-500 font-sans text-xs sm:text-sm">
        {children || message}
      </td>
    </tr>
  )
}

export default Table
