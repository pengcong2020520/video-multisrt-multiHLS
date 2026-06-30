import { Download, RefreshCcw } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CustomPlayer } from '../components/CustomPlayer'
import { ErrorNotice } from '../components/ErrorNotice'
import { EmptyState } from '../components/EmptyState'
import { LoadingBlock } from '../components/LoadingBlock'
import { PageHeader } from '../components/PageHeader'
import { useManifest, useProject } from '../hooks/useApi'
import { languageLabel } from '../lib/options'

export function PreviewPage() {
  const { projectId } = useParams()
  const [versionId, setVersionId] = useState('')
  const projectQuery = useProject(projectId)
  const manifestQuery = useManifest(projectId, versionId || undefined)

  return (
    <div className="space-y-5">
      <PageHeader
        title="网页预览"
        description={manifestQuery.data ? `版本 ${manifestQuery.data.version_id}` : projectId}
        actions={
          <>
            <button className="btn" onClick={() => void manifestQuery.refetch()} disabled={manifestQuery.isFetching}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              刷新
            </button>
            {projectId ? (
              <Link className="btn" to={`/projects/${projectId}/downloads`}>
                <Download className="h-4 w-4" aria-hidden="true" />
                下载
              </Link>
            ) : null}
          </>
        }
      />

      <div className="grid gap-3 rounded-lg border border-line bg-white p-3 md:grid-cols-[220px_1fr]">
        <label className="text-sm font-medium text-slate-700">
          <span className="mb-1 block">版本 ID</span>
          <input
            className="field"
            value={versionId}
            onChange={(event) => setVersionId(event.target.value)}
            placeholder="默认最新"
          />
        </label>
        <div className="flex flex-wrap items-end gap-2 text-sm text-slate-600">
          {(projectQuery.data?.languages || []).map((language) => (
            <span key={language} className="rounded-md bg-slate-100 px-2 py-1">
              {languageLabel(language)}
            </span>
          ))}
        </div>
      </div>

      <ErrorNotice error={manifestQuery.error || projectQuery.error} />
      {manifestQuery.isLoading ? <LoadingBlock /> : null}

      {manifestQuery.data ? (
        <div className="space-y-5">
          <CustomPlayer manifest={manifestQuery.data} />

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="panel">
              <div className="panel-header">
                <h2 className="text-base font-semibold">字幕</h2>
              </div>
              <div className="panel-body space-y-2">
                {manifestQuery.data.subtitles.map((subtitle) => (
                  <a
                    key={`${subtitle.language}-${subtitle.url}`}
                    className="flex items-center justify-between rounded-md border border-line px-3 py-2 text-sm hover:border-slate-400"
                    href={subtitle.url}
                    download
                  >
                    <span>{subtitle.label}</span>
                    <span className="text-slate-500">{subtitle.format.toUpperCase()}</span>
                  </a>
                ))}
                {!manifestQuery.data.subtitles.length ? <div className="text-sm text-slate-500">暂无字幕</div> : null}
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="text-base font-semibold">音轨</h2>
              </div>
              <div className="panel-body space-y-2">
                {manifestQuery.data.audio_tracks.map((track) => (
                  <a
                    key={`${track.language}-${track.url}`}
                    className="flex items-center justify-between rounded-md border border-line px-3 py-2 text-sm hover:border-slate-400"
                    href={track.url}
                    download
                  >
                    <span>{track.label}</span>
                    <span className="text-slate-500">{languageLabel(track.language)}</span>
                  </a>
                ))}
                {!manifestQuery.data.audio_tracks.length ? <div className="text-sm text-slate-500">暂无音轨</div> : null}
              </div>
            </div>
          </section>
        </div>
      ) : null}

      {!manifestQuery.isLoading && !manifestQuery.data && !manifestQuery.error ? (
        <EmptyState title="暂无 Manifest">完成打包后可预览。</EmptyState>
      ) : null}
    </div>
  )
}
