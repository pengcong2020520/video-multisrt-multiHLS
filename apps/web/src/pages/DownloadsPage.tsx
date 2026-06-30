import { Archive, Download, PackagePlus, RefreshCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ErrorNotice } from '../components/ErrorNotice'
import { EmptyState } from '../components/EmptyState'
import { LoadingBlock } from '../components/LoadingBlock'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { useCreatePackage, useManifest, useProject } from '../hooks/useApi'
import { formatBytes, formatDateTime } from '../lib/format'
import { languageLabel } from '../lib/options'

export function DownloadsPage() {
  const { projectId } = useParams()
  const projectQuery = useProject(projectId)
  const manifestQuery = useManifest(projectId)
  const createPackage = useCreatePackage(projectId)
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([])
  const [includeIntermediateAssets, setIncludeIntermediateAssets] = useState(true)
  const [packageResult, setPackageResult] = useState<string | null>(null)

  const languages = projectQuery.data?.languages || []

  useEffect(() => {
    if (!selectedLanguages.length && languages.length) {
      setSelectedLanguages(languages)
    }
  }, [languages, selectedLanguages.length])

  const manifestDownloads = useMemo(() => {
    const manifest = manifestQuery.data
    if (!manifest) {
      return []
    }
    return [
      ...manifest.subtitles.map((item) => ({
        key: `subtitle-${item.language}-${item.url}`,
        label: item.label,
        type: `subtitle_${item.format}`,
        language: item.language,
        url: item.url,
      })),
      ...manifest.audio_tracks.map((item) => ({
        key: `audio-${item.language}-${item.url}`,
        label: item.label,
        type: 'audio_track',
        language: item.language,
        url: item.url,
      })),
      ...manifest.downloads.map((item) => ({
        key: `download-${item.type}-${item.url}`,
        label: item.label,
        type: item.type,
        language: null,
        url: item.url,
      })),
      {
        key: 'manifest-json',
        label: 'manifest.json',
        type: 'manifest',
        language: null,
        url: '',
      },
    ]
  }, [manifestQuery.data])

  function toggleLanguage(language: string) {
    setSelectedLanguages((current) =>
      current.includes(language)
        ? current.filter((item) => item !== language)
        : [...current, language],
    )
  }

  async function requestPackage() {
    if (!manifestQuery.data || !selectedLanguages.length) {
      return
    }
    const response = await createPackage.mutateAsync({
      version_id: manifestQuery.data.version_id,
      languages: selectedLanguages,
      include_intermediate_assets: includeIntermediateAssets,
    })
    setPackageResult(`${response.package_id} · ${response.status}`)
  }

  function downloadManifest() {
    if (!manifestQuery.data) {
      return
    }
    const blob = new Blob([JSON.stringify(manifestQuery.data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${manifestQuery.data.project_id}-${manifestQuery.data.version_id}-manifest.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="结果下载"
        description={manifestQuery.data ? `版本 ${manifestQuery.data.version_id}` : projectId}
        actions={
          <button className="btn" onClick={() => void manifestQuery.refetch()} disabled={manifestQuery.isFetching}>
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            刷新
          </button>
        }
      />

      <ErrorNotice error={projectQuery.error || manifestQuery.error || createPackage.error} />
      {projectQuery.isLoading || manifestQuery.isLoading ? <LoadingBlock /> : null}

      <section className="panel">
        <div className="panel-header">
          <h2 className="text-base font-semibold">请求打包</h2>
        </div>
        <div className="panel-body grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {languages.map((language) => (
                <label key={language} className="flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedLanguages.includes(language)}
                    onChange={() => toggleLanguage(language)}
                  />
                  {languageLabel(language)}
                </label>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeIntermediateAssets}
                onChange={(event) => setIncludeIntermediateAssets(event.target.checked)}
              />
              包含中间产物
            </label>
            {packageResult ? <div className="text-sm text-accent">{packageResult}</div> : null}
          </div>
          <div className="flex items-start">
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => void requestPackage()}
              disabled={!manifestQuery.data || !selectedLanguages.length || createPackage.isPending}
            >
              <PackagePlus className="h-4 w-4" aria-hidden="true" />
              打包
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2 className="text-base font-semibold">可下载文件</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="px-3 py-3">名称</th>
                <th className="px-3 py-3">类型</th>
                <th className="px-3 py-3">语言</th>
                <th className="px-3 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {manifestDownloads.map((item) => (
                <tr key={item.key}>
                  <td className="table-cell">{item.label}</td>
                  <td className="table-cell">{item.type}</td>
                  <td className="table-cell">{languageLabel(item.language)}</td>
                  <td className="table-cell">
                    {item.type === 'manifest' ? (
                      <button className="btn" type="button" onClick={downloadManifest}>
                        <Download className="h-4 w-4" aria-hidden="true" />
                        下载
                      </button>
                    ) : (
                      <a className="btn" href={item.url} download>
                        <Download className="h-4 w-4" aria-hidden="true" />
                        下载
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!manifestDownloads.length ? (
            <div className="px-4 py-8">
              <EmptyState title="暂无下载文件">完成字幕、音轨或打包后会显示授权下载链接。</EmptyState>
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2 className="text-base font-semibold">资产索引</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="px-3 py-3">Asset</th>
                <th className="px-3 py-3">类型</th>
                <th className="px-3 py-3">语言</th>
                <th className="px-3 py-3">格式</th>
                <th className="px-3 py-3">大小</th>
                <th className="px-3 py-3">创建时间</th>
              </tr>
            </thead>
            <tbody>
              {(projectQuery.data?.assets || []).map((asset) => (
                <tr key={asset.asset_id}>
                  <td className="table-cell">
                    <div className="flex items-center gap-2">
                      <Archive className="h-4 w-4 text-slate-500" aria-hidden="true" />
                      {asset.asset_id}
                    </div>
                  </td>
                  <td className="table-cell">{asset.type}</td>
                  <td className="table-cell">{languageLabel(asset.language)}</td>
                  <td className="table-cell">{asset.format || '-'}</td>
                  <td className="table-cell">{formatBytes(asset.size_bytes)}</td>
                  <td className="table-cell">{formatDateTime(asset.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!projectQuery.data?.assets.length ? <div className="px-4 py-8 text-sm text-slate-500">暂无资产</div> : null}
        </div>
      </section>

      {projectQuery.data?.tasks.length ? (
        <section className="panel">
          <div className="panel-header">
            <h2 className="text-base font-semibold">打包任务</h2>
          </div>
          <div className="panel-body flex flex-wrap gap-2">
            {projectQuery.data.tasks
              .filter((task) => task.type === 'package_outputs')
              .map((task) => (
                <span key={task.task_id} className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm">
                  {task.task_id}
                  <StatusBadge status={task.status} />
                </span>
              ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
