import { RefreshCcw } from 'lucide-react'
import { useQueries } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { getKnownRuns } from '../api/projectStore'
import { queryKeys } from '../api/queryKeys'
import { EmptyState } from '../components/EmptyState'
import { ErrorNotice } from '../components/ErrorNotice'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { formatDateTime } from '../lib/format'

const DEFAULT_SKILLS = [
  ['media.probe', 'ffmpeg'],
  ['media.extract_audio', 'ffmpeg'],
  ['audio.separate_sources', 'demucs'],
  ['asr.transcribe', 'faster-whisper'],
  ['asr.diarize', 'whisperx'],
  ['transcript.normalize_segments', 'local'],
  ['localization.translate', 'deepseek'],
  ['subtitle.generate', 'local'],
  ['voice.synthesize', 'minimax'],
  ['audio.stitch_vocals', 'ffmpeg'],
  ['audio.mix', 'ffmpeg'],
  ['package.manifest', 'local'],
  ['package.zip', 'zip'],
] as const

export function SkillsPage() {
  const recentRuns = getKnownRuns().slice(0, 8)
  const runQueries = useQueries({
    queries: recentRuns.map((run) => ({
      queryKey: queryKeys.agentRun(run.run_id),
      queryFn: () => apiClient.getAgentRun(run.run_id),
      staleTime: 30_000,
    })),
  })

  const runData = runQueries.flatMap((query) => (query.data ? [query.data] : []))
  const queryError = runQueries.find((query) => query.error)?.error

  const providerBySkill = new Map<string, string>()
  for (const run of runData) {
    for (const skill of run.skill_runs) {
      if (skill.provider && !providerBySkill.has(skill.skill_name)) {
        providerBySkill.set(skill.skill_name, skill.provider)
      }
    }
  }

  const recentFailures = runData.flatMap((run) =>
    run.skill_runs
      .filter((skill) => skill.error)
      .map((skill) => ({
        ...skill,
        run_id: run.agent_run.run_id,
        updated_at: run.agent_run.updated_at,
      })),
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Skill 配置"
        description="已启用 Skill、默认 provider 和最近失败记录。"
        actions={
          <button
            className="btn"
            onClick={() => runQueries.forEach((query) => void query.refetch())}
            disabled={runQueries.some((query) => query.isFetching)}
          >
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            刷新
          </button>
        }
      />

      <ErrorNotice error={queryError} />

      <section className="panel">
        <div className="panel-header">
          <h2 className="text-base font-semibold">已启用 Skill</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="px-3 py-3">Skill</th>
                <th className="px-3 py-3">版本</th>
                <th className="px-3 py-3">状态</th>
                <th className="px-3 py-3">默认 Provider</th>
                <th className="px-3 py-3">超时</th>
                <th className="px-3 py-3">重试</th>
              </tr>
            </thead>
            <tbody>
              {DEFAULT_SKILLS.map(([skillName, defaultProvider]) => (
                <tr key={skillName}>
                  <td className="table-cell font-medium">{skillName}</td>
                  <td className="table-cell">1.0.0</td>
                  <td className="table-cell">
                    <StatusBadge status="succeeded" />
                  </td>
                  <td className="table-cell">{providerBySkill.get(skillName) || defaultProvider}</td>
                  <td className="table-cell">{skillName.startsWith('voice') ? 120 : 60}s</td>
                  <td className="table-cell">2</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2 className="text-base font-semibold">最近 Agent Run</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="px-3 py-3">Run</th>
                <th className="px-3 py-3">项目</th>
                <th className="px-3 py-3">状态</th>
                <th className="px-3 py-3">模板</th>
                <th className="px-3 py-3">更新时间</th>
              </tr>
            </thead>
            <tbody>
              {runData.map((run) => (
                <tr key={run.agent_run.run_id}>
                  <td className="table-cell">{run.agent_run.run_id}</td>
                  <td className="table-cell">{run.agent_run.project_id}</td>
                  <td className="table-cell">
                    <StatusBadge status={run.agent_run.status} />
                  </td>
                  <td className="table-cell">{run.agent_run.template}</td>
                  <td className="table-cell">{formatDateTime(run.agent_run.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!runData.length ? (
            <div className="px-4 py-8">
              <EmptyState title="暂无最近 Run">提交处理后会显示运行记录。</EmptyState>
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2 className="text-base font-semibold">最近失败原因</h2>
        </div>
        <div className="panel-body space-y-2">
          {recentFailures.map((failure) => (
            <div
              key={failure.skill_run_id}
              className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900"
            >
              {failure.skill_name} · {failure.error?.code} · {failure.error?.message}
            </div>
          ))}
          {!recentFailures.length ? <div className="text-sm text-slate-500">暂无失败记录</div> : null}
        </div>
      </section>
    </div>
  )
}
