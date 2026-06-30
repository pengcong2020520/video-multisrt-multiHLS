import { ArrowRight, Combine, Play, RefreshCcw, Save, Scissors, Volume2 } from 'lucide-react'
import { SyntheticEvent, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorNotice } from '../components/ErrorNotice'
import { EmptyState } from '../components/EmptyState'
import { LoadingBlock } from '../components/LoadingBlock'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import {
  useAgentRun,
  useContinueRun,
  useGenerateProject,
  usePatchSegment,
  useProject,
  useProjectLastRun,
  useSegments,
} from '../hooks/useApi'
import { formatDuration } from '../lib/format'
import { languageLabel } from '../lib/options'
import type { PatchSegmentRequest, SegmentBundle } from '../api/types'

interface RowDraft {
  start_ms: string
  end_ms: string
  speaker_id: string
  source_text: string
  translation: string
  voice_id: string
  locked: boolean
}

function draftFromBundle(bundle: SegmentBundle): RowDraft {
  return {
    start_ms: String(bundle.segment.start_ms),
    end_ms: String(bundle.segment.end_ms),
    speaker_id: bundle.segment.speaker_id || '',
    source_text: bundle.segment.source_text,
    translation: bundle.translation?.text || '',
    voice_id: bundle.tts_job?.voice_id || '',
    locked: bundle.segment.locked,
  }
}

export function ProofreadPage() {
  const { projectId } = useParams()
  const projectQuery = useProject(projectId)
  const [targetLanguage, setTargetLanguage] = useState<string | undefined>()
  const segmentsQuery = useSegments(projectId, targetLanguage)
  const patchSegment = usePatchSegment(projectId, targetLanguage)
  const generate = useGenerateProject(projectId)
  const { runId } = useProjectLastRun(projectId)
  const runQuery = useAgentRun(runId)
  const continueRun = useContinueRun(runId)
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({})
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const [staleIds, setStaleIds] = useState<string[]>([])

  const languages = projectQuery.data?.languages || projectQuery.data?.project.target_languages || []
  useEffect(() => {
    if (!targetLanguage && languages.length) {
      setTargetLanguage(languages[0])
    }
  }, [languages, targetLanguage])

  useEffect(() => {
    const next: Record<string, RowDraft> = {}
    for (const bundle of segmentsQuery.data?.segments || []) {
      next[bundle.segment.segment_id] = draftFromBundle(bundle)
    }
    setDrafts(next)
  }, [segmentsQuery.data?.segments])

  const bundles = segmentsQuery.data?.segments || []
  const selectedLanguage = targetLanguage || languages[0]

  const stats = useMemo(() => {
    const total = bundles.length
    const locked = bundles.filter((bundle) => bundle.segment.locked).length
    const failedTts = bundles.filter((bundle) => bundle.tts_job?.status === 'failed').length
    return { total, locked, failedTts }
  }, [bundles])

  function updateDraft(segmentId: string, patch: Partial<RowDraft>) {
    setDrafts((current) => ({
      ...current,
      [segmentId]: {
        ...current[segmentId],
        ...patch,
      },
    }))
  }

  function toggleSelected(segmentId: string) {
    setSelectedIds((current) =>
      current.includes(segmentId)
        ? current.filter((item) => item !== segmentId)
        : [...current, segmentId],
    )
  }

  async function saveSegment(bundle: SegmentBundle) {
    const draft = drafts[bundle.segment.segment_id]
    if (!draft || !selectedLanguage) {
      return
    }

    const payload: PatchSegmentRequest = {}
    const startMs = Number(draft.start_ms)
    const endMs = Number(draft.end_ms)
    if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || startMs >= endMs) {
      setNotice('时间轴必须为有效数字，且开始时间小于结束时间。')
      return
    }
    if (startMs !== bundle.segment.start_ms) payload.start_ms = startMs
    if (endMs !== bundle.segment.end_ms) payload.end_ms = endMs
    if ((draft.speaker_id || null) !== bundle.segment.speaker_id) {
      payload.speaker_id = draft.speaker_id || null
    }
    if (draft.source_text !== bundle.segment.source_text) {
      payload.source_text = draft.source_text
    }
    if (draft.locked !== bundle.segment.locked) {
      payload.locked = draft.locked
    }
    if (draft.translation !== (bundle.translation?.text || '')) {
      payload.translations = {
        [selectedLanguage]: draft.translation,
      }
    }

    if (!Object.keys(payload).length) {
      setNotice('当前句段没有需要保存的修改。')
      return
    }

    await patchSegment.mutateAsync({ segmentId: bundle.segment.segment_id, payload })
    setStaleIds((current) =>
      current.includes(bundle.segment.segment_id) ? current : [...current, bundle.segment.segment_id],
    )
    setNotice('已保存，相关字幕和 TTS 需要重新生成。')
  }

  async function rerunSegment(segmentId: string) {
    if (!selectedLanguage) {
      return
    }
    const run = await generate.mutateAsync({
      target_language: selectedLanguage,
      scope: 'segments',
      steps: ['subtitle', 'tts', 'mix'],
      segment_ids: [segmentId],
      agent_template: 'rerun_segments',
    })
    setNotice(`已创建局部重跑 ${run.run_id}`)
  }

  async function rerunLanguage() {
    if (!selectedLanguage) {
      return
    }
    const run = await generate.mutateAsync({
      target_language: selectedLanguage,
      scope: 'language',
      steps: ['subtitle', 'tts', 'mix'],
      segment_ids: [],
      agent_template: 'full_dubbing',
    })
    setNotice(`已创建语言重跑 ${run.run_id}`)
  }

  async function continueAfterProofreading() {
    await continueRun.mutateAsync({
      checkpoint: runQuery.data?.current_checkpoint || 'proofreading',
      confirmed: true,
    })
    setNotice('已继续 Agent Run。')
  }

  function handleMergeOrSplit(event: SyntheticEvent, action: 'merge' | 'split') {
    event.preventDefault()
    if (action === 'merge' && selectedIds.length < 2) {
      setNotice('请选择至少两个相邻句段。')
      return
    }
    if (action === 'split' && selectedIds.length !== 1) {
      setNotice('请选择一个句段。')
      return
    }
    setNotice('合并/拆分入口已保留，当前 Spec API 仅开放单句 PATCH 保存。')
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="校对编辑"
        description={projectId ? `项目 ${projectId}` : undefined}
        actions={
          <>
            <button className="btn" type="button" onClick={() => void rerunLanguage()} disabled={!selectedLanguage || generate.isPending}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              重跑语言
            </button>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => void continueAfterProofreading()}
              disabled={runQuery.data?.agent_run.status !== 'waiting_human' || continueRun.isPending}
            >
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
              继续
            </button>
            {projectId ? (
              <Link className="btn" to={`/projects/${projectId}/preview`}>
                预览
              </Link>
            ) : null}
          </>
        }
      />

      <ErrorNotice
        error={
          projectQuery.error ||
          segmentsQuery.error ||
          patchSegment.error ||
          generate.error ||
          continueRun.error
        }
      />

      <div className="grid gap-3 rounded-lg border border-line bg-white p-3 lg:grid-cols-[1fr_auto]">
        <div className="flex flex-wrap gap-2">
          {languages.map((language) => (
            <button
              key={language}
              className={`btn ${selectedLanguage === language ? 'btn-primary' : ''}`}
              type="button"
              onClick={() => setTargetLanguage(language)}
            >
              {languageLabel(language)}
            </button>
          ))}
        </div>
        <form className="flex gap-2" onSubmit={(event) => handleMergeOrSplit(event, 'merge')}>
          <button className="btn" type="submit">
            <Combine className="h-4 w-4" aria-hidden="true" />
            合并
          </button>
          <button className="btn" type="button" onClick={(event) => handleMergeOrSplit(event, 'split')}>
            <Scissors className="h-4 w-4" aria-hidden="true" />
            拆分
          </button>
        </form>
      </div>

      {notice ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-3">
          <div className="text-xs text-slate-500">句段</div>
          <div className="mt-1 text-xl font-semibold">{stats.total}</div>
        </div>
        <div className="panel p-3">
          <div className="text-xs text-slate-500">已锁定</div>
          <div className="mt-1 text-xl font-semibold">{stats.locked}</div>
        </div>
        <div className="panel p-3">
          <div className="text-xs text-slate-500">TTS 失败</div>
          <div className="mt-1 text-xl font-semibold">{stats.failedTts}</div>
        </div>
      </div>

      {projectQuery.isLoading || segmentsQuery.isLoading ? <LoadingBlock /> : null}

      {!segmentsQuery.isLoading && !bundles.length ? (
        <EmptyState title="暂无句段">处理到 ASR/翻译阶段后会出现校对表格。</EmptyState>
      ) : null}

      {bundles.length ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-white">
          <table className="w-full min-w-[1280px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="px-3 py-3">选择</th>
                <th className="px-3 py-3">时间</th>
                <th className="px-3 py-3">说话人</th>
                <th className="px-3 py-3">原文</th>
                <th className="px-3 py-3">译文</th>
                <th className="px-3 py-3">音色</th>
                <th className="px-3 py-3">状态</th>
                <th className="px-3 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {bundles.map((bundle) => {
                const segmentId = bundle.segment.segment_id
                const draft = drafts[segmentId] || draftFromBundle(bundle)
                const stale = staleIds.includes(segmentId)
                return (
                  <tr key={segmentId} className={bundle.segment.locked ? 'bg-amber-50/40' : undefined}>
                    <td className="table-cell">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(segmentId)}
                        onChange={() => toggleSelected(segmentId)}
                        aria-label={`选择 ${segmentId}`}
                      />
                      <div className="mt-2 text-xs text-slate-500">#{bundle.segment.index}</div>
                    </td>
                    <td className="table-cell w-36">
                      <div className="grid gap-2">
                        <input
                          className="field"
                          value={draft.start_ms}
                          onChange={(event) => updateDraft(segmentId, { start_ms: event.target.value })}
                          aria-label={`${segmentId} start_ms`}
                        />
                        <input
                          className="field"
                          value={draft.end_ms}
                          onChange={(event) => updateDraft(segmentId, { end_ms: event.target.value })}
                          aria-label={`${segmentId} end_ms`}
                        />
                        <div className="text-xs text-slate-500">
                          {formatDuration(bundle.segment.end_ms - bundle.segment.start_ms)}
                        </div>
                      </div>
                    </td>
                    <td className="table-cell w-40">
                      <input
                        className="field"
                        value={draft.speaker_id}
                        onChange={(event) => updateDraft(segmentId, { speaker_id: event.target.value })}
                        placeholder="spk_1"
                      />
                    </td>
                    <td className="table-cell w-72">
                      <textarea
                        className="textarea"
                        value={draft.source_text}
                        onChange={(event) => updateDraft(segmentId, { source_text: event.target.value })}
                      />
                      {bundle.segment.quality_flags.length ? (
                        <div className="mt-1 text-xs text-amber-700">
                          {bundle.segment.quality_flags.join('、')}
                        </div>
                      ) : null}
                    </td>
                    <td className="table-cell w-80">
                      <textarea
                        className="textarea"
                        value={draft.translation}
                        onChange={(event) => updateDraft(segmentId, { translation: event.target.value })}
                        aria-label={`${segmentId} translation`}
                      />
                      {bundle.translation ? (
                        <div className="mt-1 text-xs text-slate-500">
                          {bundle.translation.model || '-'} · {bundle.translation.prompt_version || '-'}
                        </div>
                      ) : null}
                    </td>
                    <td className="table-cell w-44">
                      <input
                        className="field"
                        value={draft.voice_id}
                        onChange={(event) => updateDraft(segmentId, { voice_id: event.target.value })}
                        placeholder="voice_id"
                      />
                    </td>
                    <td className="table-cell w-36">
                      <div className="space-y-2">
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={draft.locked}
                            onChange={(event) => updateDraft(segmentId, { locked: event.target.checked })}
                          />
                          locked
                        </label>
                        {bundle.tts_job ? <StatusBadge status={bundle.tts_job.status} /> : <span className="text-xs text-slate-500">未生成</span>}
                        {stale ? <div className="text-xs text-warn">下游产物待重跑</div> : null}
                      </div>
                    </td>
                    <td className="table-cell w-52">
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="btn btn-primary"
                          type="button"
                          onClick={() => void saveSegment(bundle)}
                          disabled={patchSegment.isPending}
                        >
                          <Save className="h-4 w-4" aria-hidden="true" />
                          保存
                        </button>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => setNotice('单句试听入口已打开；当前 API 未返回分段音频 URL。')}
                          disabled={!bundle.tts_job?.output_asset_id}
                          title={bundle.tts_job?.output_asset_id ? '试听' : '暂无分段音频'}
                        >
                          <Volume2 className="h-4 w-4" aria-hidden="true" />
                          试听
                        </button>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => void rerunSegment(segmentId)}
                          disabled={generate.isPending}
                        >
                          <Play className="h-4 w-4" aria-hidden="true" />
                          重跑
                        </button>
                      </div>
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
