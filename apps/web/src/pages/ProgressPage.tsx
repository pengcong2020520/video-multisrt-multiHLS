import { ArrowRight, Play, RefreshCcw, RotateCcw } from 'lucide-react'
import { FormEvent, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { errorCodeToMessage } from '../api/errors'
import { ErrorNotice } from '../components/ErrorNotice'
import { EmptyState } from '../components/EmptyState'
import { LoadingBlock } from '../components/LoadingBlock'
import { PageHeader } from '../components/PageHeader'
import { ProgressBar } from '../components/ProgressBar'
import { StatusBadge } from '../components/StatusBadge'
import {
  useAgentRun,
  useContinueRun,
  useGenerateProject,
  useProject,
  useProjectLastRun,
} from '../hooks/useApi'
import { formatDateTime } from '../lib/format'
import { languageLabel, STAGE_LABELS } from '../lib/options'

const STAGE_ORDER = [
  'planning',
  'media.probe',
  'media.extract_audio',
  'audio.separate_sources',
  'asr.transcribe',
  'asr.diarize',
  'transcript.normalize_segments',
  'localization.translate',
  'proofreading',
  'voice.synthesize',
  'audio.stitch_vocals',
  'audio.mix',
  'package.manifest',
  'package.zip',
  'completed',
]

function stagePercent(step: string | null | undefined, status: string | undefined) {
  if (status === 'succeeded') {
    return 100
  }
  if (status === 'failed' || !step) {
    return status === 'failed' ? 100 : 5
  }
  const index = Math.max(0, STAGE_ORDER.indexOf(step))
  return ((index + 1) / STAGE_ORDER.length) * 100
}

export function ProgressPage() {
  const { projectId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryRunId = searchParams.get('run_id') || undefined
  const { runId: lastRunId } = useProjectLastRun(projectId)
  const activeRunId = queryRunId || lastRunId
  const [manualRunId, setManualRunId] = useState(activeRunId || '')
  const projectQuery = useProject(projectId)
  const runQuery = useAgentRun(activeRunId, true)
  const continueRun = useContinueRun(activeRunId)
  const generate = useGenerateProject(projectId)

  const run = runQuery.data?.agent_run
  const currentStage = runQuery.data?.current_checkpoint || run?.current_step || run?.status
  const progress = stagePercent(currentStage, run?.status)

  const taskErrors = useMemo(() => {
    return (projectQuery.data?.tasks || []).filter((task) => task.error_code || task.error_message)
  }, [projectQuery.data?.tasks])

  const skillErrors = useMemo(() => {
    return (runQuery.data?.skill_runs || []).filter((skill) => skill.error)
  }, [runQuery.data?.skill_runs])

  function handleManualRun(event: FormEvent) {
    event.preventDefault()
    const trimmed = manualRunId.trim()
    if (trimmed) {
      setSearchParams({ run_id: trimmed })
    }
  }

  async function handleContinue() {
    await continueRun.mutateAsync({
      checkpoint: runQuery.data?.current_checkpoint || 'proofreading',
      confirmed: true,
    })
  }

  async function handleRetry() {
    const targetLanguage = run?.target_languages[0] || projectQuery.data?.languages[0]
    if (!targetLanguage) {
      return
    }
    await generate.mutateAsync({
      target_language: targetLanguage,
      scope: 'language',
      steps: ['subtitle', 'tts', 'mix'],
      segment_ids: [],
      agent_template: 'full_dubbing',
    })
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="处理进度"
        description={projectId ? `项目 ${projectId}` : undefined}
        actions={
          <>
            {projectId ? (
              <Link className="btn" to={`/projects/${projectId}/proofread`}>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
                校对
              </Link>
            ) : null}
            <button className="btn" onClick={() => void runQuery.refetch()} disabled={runQuery.isFetching}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              刷新
            </button>
          </>
        }
      />

      <form className="flex max-w-xl gap-2" onSubmit={handleManualRun}>
        <input
          className="field"
          value={manualRunId}
          onChange={(event) => setManualRunId(event.target.value)}
          placeholder="run_..."
        />
        <button className="btn" type="submit">
          打开 Run
        </button>
      </form>

      <ErrorNotice error={projectQuery.error || runQuery.error || continueRun.error || generate.error} />

      {!activeRunId ? (
        <EmptyState title="未找到最近 Run">输入 run_id 或从上传页提交处理。</EmptyState>
      ) : null}

      {runQuery.isLoading ? <LoadingBlock /> : null}

      {run ? (
        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="panel">
            <div className="panel-header flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Agent Run</h2>
                <div className="mt-1 text-xs text-slate-500">{run.run_id}</div>
              </div>
              <StatusBadge status={run.status} />
            </div>
            <div className="panel-body space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-medium">{STAGE_LABELS[currentStage || ''] || currentStage || '-'}</span>
                  <span className="text-slate-500">{Math.round(progress)}%</span>
                </div>
                <ProgressBar value={progress} />
              </div>

              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-500">模板</dt>
                  <dd className="font-medium">{run.template}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">版本</dt>
                  <dd className="font-medium">{run.version_id || '-'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">源语言</dt>
                  <dd className="font-medium">{languageLabel(run.source_language)}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">目标语言</dt>
                  <dd className="font-medium">{run.target_languages.map(languageLabel).join(', ')}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">创建时间</dt>
                  <dd className="font-medium">{formatDateTime(run.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">更新时间</dt>
                  <dd className="font-medium">{formatDateTime(run.updated_at)}</dd>
                </div>
              </dl>

              {runQuery.data?.quality_flags.length ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  {runQuery.data.quality_flags.join('、')}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() => void handleContinue()}
                  disabled={run.status !== 'waiting_human' || continueRun.isPending}
                >
                  <Play className="h-4 w-4" aria-hidden="true" />
                  继续
                </button>
                <button
                  className="btn"
                  type="button"
                  onClick={() => void handleRetry()}
                  disabled={generate.isPending || !['failed', 'canceled'].includes(run.status)}
                >
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                  重试
                </button>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2 className="text-base font-semibold">Skill Run</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse">
                <thead className="table-head">
                  <tr>
                    <th className="px-3 py-3">Skill</th>
                    <th className="px-3 py-3">状态</th>
                    <th className="px-3 py-3">语言</th>
                    <th className="px-3 py-3">Provider</th>
                    <th className="px-3 py-3">开始</th>
                    <th className="px-3 py-3">结束</th>
                  </tr>
                </thead>
                <tbody>
                  {(runQuery.data?.skill_runs || []).map((skill) => (
                    <tr key={skill.skill_run_id}>
                      <td className="table-cell">
                        <div className="font-medium">{skill.skill_name}</div>
                        <div className="text-xs text-slate-500">v{skill.skill_version}</div>
                        {skill.error ? (
                          <div className="mt-1 text-xs text-red-700">
                            {errorCodeToMessage(skill.error.code)}: {skill.error.message}
                          </div>
                        ) : null}
                      </td>
                      <td className="table-cell">
                        <StatusBadge status={skill.status} />
                      </td>
                      <td className="table-cell">{languageLabel(skill.target_language)}</td>
                      <td className="table-cell">
                        <div>{skill.provider || '-'}</div>
                        <div className="text-xs text-slate-500">{skill.model || ''}</div>
                      </td>
                      <td className="table-cell">{formatDateTime(skill.started_at)}</td>
                      <td className="table-cell">{formatDateTime(skill.finished_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!runQuery.data?.skill_runs.length ? (
                <div className="px-4 py-8 text-center text-sm text-slate-500">暂无 Skill Run</div>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {taskErrors.length || skillErrors.length ? (
        <section className="panel">
          <div className="panel-header">
            <h2 className="text-base font-semibold">错误</h2>
          </div>
          <div className="panel-body space-y-2 text-sm">
            {taskErrors.map((task) => (
              <div key={task.task_id} className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-900">
                {task.type}: {errorCodeToMessage(task.error_code)} {task.error_message || ''}
              </div>
            ))}
            {skillErrors.map((skill) => (
              <div key={skill.skill_run_id} className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-900">
                {skill.skill_name}: {errorCodeToMessage(skill.error?.code)} {skill.error?.message}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
