import { AlertTriangle } from 'lucide-react'
import { getErrorMessage } from '../api/errors'

export function ErrorNotice({ error, title = '请求失败' }: { error: unknown; title?: string }) {
  if (!error) {
    return null
  }
  return (
    <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-900">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>
        <div className="font-semibold">{title}</div>
        <div>{getErrorMessage(error)}</div>
      </div>
    </div>
  )
}
