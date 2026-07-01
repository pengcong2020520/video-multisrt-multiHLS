import { Check, Download, Loader2, Plus, RefreshCcw, Subtitles, Volume2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { AgentRunStatus, TargetLanguage } from '../api/types'
import { CustomPlayer } from '../components/CustomPlayer'
import { ErrorNotice } from '../components/ErrorNotice'
import { EmptyState } from '../components/EmptyState'
import { LoadingBlock } from '../components/LoadingBlock'
import { PageHeader } from '../components/PageHeader'
import {
  useAgentRun,
  useDubProject,
  useManifest,
  useProject,
  useTranslateProject,
} from '../hooks/useApi'
import { TARGET_LANGUAGES, languageLabel } from '../lib/options'

type OperationKind = 'subtitle' | 'audio'

interface PendingOperation {
  key: string
  kind: OperationKind
  language: string
  runId: string
}

const DEFAULT_TARGET_LANGUAGE: TargetLanguage = 'en-US'

export function PreviewPage() {
  const { projectId } = useParams()
  const [versionId, setVersionId] = useState('')
  const [subtitleLanguage, setSubtitleLanguage] = useState('none')
  const [audioLanguage, setAudioLanguage] = useState('video')
  const [subtitleTarget, setSubtitleTarget] = useState<TargetLanguage>(DEFAULT_TARGET_LANGUAGE)
  const [audioTarget, setAudioTarget] = useState<TargetLanguage>(DEFAULT_TARGET_LANGUAGE)
  const [operations, setOperations] = useState<Record<string, PendingOperation>>({})
  const projectQuery = useProject(projectId)
  const manifestQuery = useManifest(projectId, versionId || undefined)
  const translateMutation = useTranslateProject(projectId)
  const dubMutation = useDubProject(projectId)

  const subtitles = manifestQuery.data?.subtitles || []
  const audioTracks = manifestQuery.data?.audio_tracks || []
  const subtitleLanguages = useMemo(
    () => new Set(subtitles.map((subtitle) => subtitle.language)),
    [subtitles],
  )
  const audioLanguages = useMemo(
    () => new Set(audioTracks.map((track) => track.language)),
    [audioTracks],
  )
  const pendingOperations = Object.values(operations)
  const subtitleBusy = translateMutation.isPending || hasPendingOperation(pendingOperations, 'subtitle', subtitleTarget)
  const audioBusy = dubMutation.isPending || hasPendingOperation(pendingOperations, 'audio', audioTarget)
  const nextSubtitleTarget = firstAvailableLanguage(subtitleLanguages)
  const nextAudioTarget = firstAvailableLanguage(audioLanguages)

  useEffect(() => {
    if (subtitleLanguages.has(subtitleTarget) && nextSubtitleTarget) {
      setSubtitleTarget(nextSubtitleTarget)
    }
  }, [nextSubtitleTarget, subtitleLanguages, subtitleTarget])

  useEffect(() => {
    if (audioLanguages.has(audioTarget) && nextAudioTarget) {
      setAudioTarget(nextAudioTarget)
    }
  }, [audioLanguages, audioTarget, nextAudioTarget])

  function trackOperation(kind: OperationKind, language: string, runId: string) {
    const key = `${kind}:${language}:${runId}`
    setOperations((current) => ({
      ...current,
      [key]: { key, kind, language, runId },
    }))
  }

  function clearOperation(key: string) {
    setOperations((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  function handleOperationCompleted(key: string) {
    clearOperation(key)
    void manifestQuery.refetch()
    void projectQuery.refetch()
  }

  async function handleAddSubtitle() {
    if (!projectId || subtitleLanguages.has(subtitleTarget)) {
      return
    }
    const run = await translateMutation.mutateAsync({ target_language: subtitleTarget })
    trackOperation('subtitle', subtitleTarget, run.run_id)
  }

  async function handleAddAudio() {
    if (!projectId || audioLanguages.has(audioTarget)) {
      return
    }
    const run = await dubMutation.mutateAsync({ target_language: audioTarget })
    trackOperation('audio', audioTarget, run.run_id)
  }

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

      <ErrorNotice error={manifestQuery.error || projectQuery.error || translateMutation.error || dubMutation.error} />
      {manifestQuery.isLoading ? <LoadingBlock /> : null}

      {manifestQuery.data ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <CustomPlayer
              manifest={manifestQuery.data}
              subtitleLanguage={subtitleLanguage}
              audioLanguage={audioLanguage}
              onSubtitleLanguageChange={setSubtitleLanguage}
              onAudioLanguageChange={setAudioLanguage}
            />
          </div>

          <aside className="space-y-4">
            <section className="panel">
              <div className="panel-header">
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <Subtitles className="h-4 w-4" aria-hidden="true" />
                  外切字幕
                </h2>
              </div>
              <div className="panel-body space-y-3">
                <div className="space-y-2">
                  <button
                    className={selectionButtonClass(subtitleLanguage === 'none')}
                    type="button"
                    onClick={() => setSubtitleLanguage('none')}
                  >
                    <span>无字幕</span>
                    {subtitleLanguage === 'none' ? <Check className="h-4 w-4" aria-hidden="true" /> : null}
                  </button>
                  {subtitles.map((subtitle) => (
                    <button
                      key={`${subtitle.language}-${subtitle.url}`}
                      className={selectionButtonClass(subtitleLanguage === subtitle.language)}
                      type="button"
                      onClick={() => setSubtitleLanguage(subtitle.language)}
                    >
                      <span>{subtitle.label}</span>
                      <span className="flex items-center gap-2 text-slate-500">
                        {subtitle.format.toUpperCase()}
                        {subtitleLanguage === subtitle.language ? (
                          <Check className="h-4 w-4" aria-hidden="true" />
                        ) : null}
                      </span>
                    </button>
                  ))}
                  {!subtitles.length ? <div className="text-sm text-slate-500">暂无字幕</div> : null}
                </div>

                <div className="grid gap-2 sm:grid-cols-[1fr_auto] xl:grid-cols-1">
                  <select
                    className="field"
                    value={subtitleTarget}
                    onChange={(event) => setSubtitleTarget(event.target.value as TargetLanguage)}
                  >
                    {TARGET_LANGUAGES.map((language) => (
                      <option
                        key={language.value}
                        value={language.value}
                        disabled={subtitleLanguages.has(language.value)}
                      >
                        {language.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={!nextSubtitleTarget || subtitleLanguages.has(subtitleTarget) || subtitleBusy}
                    onClick={() => void handleAddSubtitle()}
                  >
                    {subtitleBusy ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Plus className="h-4 w-4" aria-hidden="true" />
                    )}
                    添加字幕
                  </button>
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <Volume2 className="h-4 w-4" aria-hidden="true" />
                  外切音轨
                </h2>
              </div>
              <div className="panel-body space-y-3">
                <div className="space-y-2">
                  <button
                    className={selectionButtonClass(audioLanguage === 'video')}
                    type="button"
                    onClick={() => setAudioLanguage('video')}
                  >
                    <span>视频内置音轨</span>
                    {audioLanguage === 'video' ? <Check className="h-4 w-4" aria-hidden="true" /> : null}
                  </button>
                  {audioTracks.map((track) => (
                    <button
                      key={`${track.language}-${track.url}`}
                      className={selectionButtonClass(audioLanguage === track.language)}
                      type="button"
                      onClick={() => setAudioLanguage(track.language)}
                    >
                      <span>{track.label}</span>
                      <span className="flex items-center gap-2 text-slate-500">
                        {languageLabel(track.language)}
                        {audioLanguage === track.language ? <Check className="h-4 w-4" aria-hidden="true" /> : null}
                      </span>
                    </button>
                  ))}
                  {!audioTracks.length ? <div className="text-sm text-slate-500">暂无外切音轨</div> : null}
                </div>

                <div className="grid gap-2 sm:grid-cols-[1fr_auto] xl:grid-cols-1">
                  <select
                    className="field"
                    value={audioTarget}
                    onChange={(event) => setAudioTarget(event.target.value as TargetLanguage)}
                  >
                    {TARGET_LANGUAGES.map((language) => (
                      <option
                        key={language.value}
                        value={language.value}
                        disabled={audioLanguages.has(language.value)}
                      >
                        {language.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={!nextAudioTarget || audioLanguages.has(audioTarget) || audioBusy}
                    onClick={() => void handleAddAudio()}
                  >
                    {audioBusy ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Plus className="h-4 w-4" aria-hidden="true" />
                    )}
                    添加配音
                  </button>
                </div>
              </div>
            </section>

            {pendingOperations.length ? (
              <section className="panel">
                <div className="panel-header">
                  <h2 className="text-base font-semibold">处理进度</h2>
                </div>
                <div className="panel-body space-y-2">
                  {pendingOperations.map((operation) => (
                    <OperationProgress
                      key={operation.key}
                      operation={operation}
                      onCompleted={handleOperationCompleted}
                      onDismiss={clearOperation}
                    />
                  ))}
                </div>
              </section>
            ) : null}
          </aside>
        </div>
      ) : null}

      {!manifestQuery.isLoading && !manifestQuery.data && !manifestQuery.error ? (
        <EmptyState title="暂无 Manifest">上传完成后可预览原视频。</EmptyState>
      ) : null}
    </div>
  )
}

function OperationProgress({
  operation,
  onCompleted,
  onDismiss,
}: {
  operation: PendingOperation
  onCompleted: (key: string) => void
  onDismiss: (key: string) => void
}) {
  const runQuery = useAgentRun(operation.runId, true)
  const notifiedRef = useRef(false)
  const status = runQuery.data?.agent_run.status
  const skillRuns = runQuery.data?.skill_runs || []
  const total = Math.max(skillRuns.length, 1)
  const completed = skillRuns.filter((run) => ['succeeded', 'failed', 'canceled'].includes(run.status)).length
  const percent = terminalPercent(status, operation.kind) ?? Math.round((completed / total) * 100)
  const failedSkill = skillRuns.find((run) => run.status === 'failed')
  const runError = runQuery.error instanceof Error ? runQuery.error.message : undefined
  const failed = Boolean(runQuery.error) || status === 'failed' || status === 'canceled'
  const completedSuccessfully = isOperationComplete(status, operation.kind)

  useEffect(() => {
    if (!notifiedRef.current && completedSuccessfully) {
      notifiedRef.current = true
      onCompleted(operation.key)
    }
  }, [completedSuccessfully, onCompleted, operation.key])

  return (
    <div className="rounded-md border border-line p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium">
            {operation.kind === 'subtitle' ? '字幕' : '配音'} · {languageLabel(operation.language)}
          </div>
          <div className={failed ? 'text-red-700' : 'text-slate-500'}>
            {progressLabel(status, operation.kind, runError || failedSkill?.error?.message)}
          </div>
        </div>
        {failed ? (
          <button
            className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
            type="button"
            onClick={() => onDismiss(operation.key)}
            aria-label="移除"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-slate-500" aria-hidden="true" />
        )}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full ${failed ? 'bg-red-600' : 'bg-accent'}`}
          style={{ width: `${Math.min(100, Math.max(8, percent))}%` }}
        />
      </div>
    </div>
  )
}

function firstAvailableLanguage(existingLanguages: Set<string>): TargetLanguage | null {
  return TARGET_LANGUAGES.find((language) => !existingLanguages.has(language.value))?.value || null
}

function hasPendingOperation(operations: PendingOperation[], kind: OperationKind, language: string): boolean {
  return operations.some((operation) => operation.kind === kind && operation.language === language)
}

function selectionButtonClass(active: boolean): string {
  return [
    'flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition',
    active ? 'border-accent bg-teal-50 text-accent' : 'border-line bg-white text-slate-700 hover:border-slate-400',
  ].join(' ')
}

function isOperationComplete(status: AgentRunStatus | string | undefined, kind: OperationKind): boolean {
  if (status === 'succeeded') {
    return true
  }
  return kind === 'subtitle' && status === 'waiting_human'
}

function terminalPercent(status: AgentRunStatus | string | undefined, kind: OperationKind): number | null {
  if (isOperationComplete(status, kind) || status === 'failed' || status === 'canceled') {
    return 100
  }
  return null
}

function progressLabel(
  status: AgentRunStatus | string | undefined,
  kind: OperationKind,
  errorMessage: string | undefined,
): string {
  if (errorMessage && (!status || status === 'failed')) {
    return errorMessage
  }
  if (!status) {
    return '等待执行'
  }
  if (isOperationComplete(status, kind)) {
    return '处理完成'
  }
  if (status === 'failed') {
    return errorMessage || '处理失败'
  }
  if (status === 'canceled') {
    return '已取消'
  }
  return '处理中'
}
