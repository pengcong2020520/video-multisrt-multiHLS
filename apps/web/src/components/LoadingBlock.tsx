export function LoadingBlock({ label = '加载中' }: { label?: string }) {
  return (
    <div className="panel">
      <div className="panel-body">
        <div className="h-2 w-28 animate-pulse rounded bg-slate-200" />
        <div className="mt-4 h-10 animate-pulse rounded bg-slate-100" />
        <div className="mt-3 h-10 animate-pulse rounded bg-slate-100" />
        <span className="sr-only">{label}</span>
      </div>
    </div>
  )
}
