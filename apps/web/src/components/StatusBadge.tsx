import { PROJECT_STATUS_LABELS, TASK_STATUS_LABELS } from '../lib/options'

const STATUS_CLASS: Record<string, string> = {
  draft: 'border-slate-300 bg-slate-100 text-slate-700',
  uploaded: 'border-sky-200 bg-sky-50 text-sky-800',
  planning: 'border-cyan-200 bg-cyan-50 text-cyan-800',
  processing: 'border-blue-200 bg-blue-50 text-blue-800',
  running: 'border-blue-200 bg-blue-50 text-blue-800',
  pending: 'border-slate-300 bg-slate-100 text-slate-700',
  proofreading: 'border-amber-200 bg-amber-50 text-amber-800',
  waiting_human: 'border-amber-200 bg-amber-50 text-amber-800',
  generating: 'border-violet-200 bg-violet-50 text-violet-800',
  retrying: 'border-violet-200 bg-violet-50 text-violet-800',
  succeeded: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  failed: 'border-red-200 bg-red-50 text-red-800',
  canceled: 'border-slate-300 bg-slate-100 text-slate-700',
  archived: 'border-slate-300 bg-slate-100 text-slate-700',
}

export function StatusBadge({ status }: { status: string }) {
  const label = PROJECT_STATUS_LABELS[status] || TASK_STATUS_LABELS[status] || status
  return (
    <span
      className={`inline-flex h-6 items-center rounded-md border px-2 text-xs font-medium ${
        STATUS_CLASS[status] || 'border-slate-300 bg-slate-100 text-slate-700'
      }`}
    >
      {label}
    </span>
  )
}
