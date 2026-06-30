import { clampPercent } from '../lib/format'

export function ProgressBar({ value }: { value: number }) {
  const percent = clampPercent(value)
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200" aria-label={`进度 ${percent}%`}>
      <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${percent}%` }} />
    </div>
  )
}
