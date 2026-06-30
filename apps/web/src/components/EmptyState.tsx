import type { ReactNode } from 'react'

export function EmptyState({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-white px-6 py-10 text-center">
      <div className="text-sm font-semibold text-ink">{title}</div>
      {children ? <div className="mt-2 text-sm text-slate-600">{children}</div> : null}
    </div>
  )
}
