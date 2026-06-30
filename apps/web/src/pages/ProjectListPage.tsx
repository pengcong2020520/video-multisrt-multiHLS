import { ExternalLink, Filter, Plus, RefreshCcw, Search } from 'lucide-react'
import { FormEvent, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ErrorNotice } from '../components/ErrorNotice'
import { EmptyState } from '../components/EmptyState'
import { LoadingBlock } from '../components/LoadingBlock'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { useKnownProjects } from '../hooks/useApi'
import { formatDateTime, formatDuration } from '../lib/format'
import { languageLabel, PROJECT_STATUS_LABELS, TARGET_LANGUAGES } from '../lib/options'

export function ProjectListPage() {
  const navigate = useNavigate()
  const { data, error, isLoading, refetch, isFetching } = useKnownProjects()
  const [status, setStatus] = useState('all')
  const [targetLanguage, setTargetLanguage] = useState('all')
  const [projectId, setProjectId] = useState('')

  const projects = useMemo(() => {
    return (data || [])
      .filter((item) => status === 'all' || item.project.status === status)
      .filter(
        (item) =>
          targetLanguage === 'all' || item.project.target_languages.includes(targetLanguage),
      )
      .sort(
        (a, b) =>
          new Date(b.project.updated_at).getTime() - new Date(a.project.updated_at).getTime(),
      )
  }, [data, status, targetLanguage])

  function handleOpenProject(event: FormEvent) {
    event.preventDefault()
    const trimmed = projectId.trim()
    if (trimmed) {
      navigate(`/projects/${encodeURIComponent(trimmed)}/progress`)
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="项目列表"
        description="按最近创建或打开的项目汇总处理状态。"
        actions={
          <>
            <button className="btn" onClick={() => void refetch()} disabled={isFetching}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              刷新
            </button>
            <Link className="btn btn-primary" to="/upload">
              <Plus className="h-4 w-4" aria-hidden="true" />
              新建
            </Link>
          </>
        }
      />

      <div className="grid gap-3 rounded-lg border border-line bg-white p-3 md:grid-cols-[180px_180px_1fr]">
        <label className="text-sm font-medium text-slate-700">
          <span className="mb-1 flex items-center gap-2">
            <Filter className="h-4 w-4" aria-hidden="true" />
            状态
          </span>
          <select className="field" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">全部</option>
            {Object.entries(PROJECT_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium text-slate-700">
          <span className="mb-1 block">目标语言</span>
          <select
            className="field"
            value={targetLanguage}
            onChange={(event) => setTargetLanguage(event.target.value)}
          >
            <option value="all">全部</option>
            {TARGET_LANGUAGES.map((language) => (
              <option key={language.value} value={language.value}>
                {language.label}
              </option>
            ))}
          </select>
        </label>

        <form className="text-sm font-medium text-slate-700" onSubmit={handleOpenProject}>
          <span className="mb-1 block">项目 ID</span>
          <div className="flex gap-2">
            <input
              className="field"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="proj_..."
            />
            <button className="btn" type="submit">
              <Search className="h-4 w-4" aria-hidden="true" />
              打开
            </button>
          </div>
        </form>
      </div>

      <ErrorNotice error={error} />

      {isLoading ? <LoadingBlock /> : null}

      {!isLoading && !projects.length ? (
        <EmptyState title="暂无项目">
          <Link className="mt-3 inline-flex text-accent hover:underline" to="/upload">
            创建第一个项目
          </Link>
        </EmptyState>
      ) : null}

      {projects.length ? (
        <div className="overflow-hidden rounded-lg border border-line bg-white">
          <table className="w-full min-w-[920px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="px-3 py-3">项目</th>
                <th className="px-3 py-3">状态</th>
                <th className="px-3 py-3">源语言</th>
                <th className="px-3 py-3">目标语言</th>
                <th className="px-3 py-3">时长</th>
                <th className="px-3 py-3">创建人</th>
                <th className="px-3 py-3">更新时间</th>
                <th className="px-3 py-3">入口</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(({ project, tasks }) => {
                const latestFailedTask = [...tasks]
                  .reverse()
                  .find((task) => task.status === 'failed' && task.error_code)
                return (
                  <tr key={project.project_id} className="hover:bg-slate-50">
                    <td className="table-cell">
                      <div className="font-medium text-ink">{project.name}</div>
                      <div className="text-xs text-slate-500">{project.project_id}</div>
                      {latestFailedTask ? (
                        <div className="mt-1 text-xs text-red-700">
                          {latestFailedTask.error_code}: {latestFailedTask.error_message}
                        </div>
                      ) : null}
                    </td>
                    <td className="table-cell">
                      <StatusBadge status={project.status} />
                    </td>
                    <td className="table-cell">{languageLabel(project.source_language)}</td>
                    <td className="table-cell">
                      <div className="flex flex-wrap gap-1">
                        {project.target_languages.map((language) => (
                          <span key={language} className="rounded-md bg-slate-100 px-2 py-1 text-xs">
                            {languageLabel(language)}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="table-cell">{formatDuration(project.duration_ms)}</td>
                    <td className="table-cell">{project.created_by}</td>
                    <td className="table-cell">{formatDateTime(project.updated_at)}</td>
                    <td className="table-cell">
                      <Link className="btn" to={`/projects/${project.project_id}/progress`}>
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                        详情
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
