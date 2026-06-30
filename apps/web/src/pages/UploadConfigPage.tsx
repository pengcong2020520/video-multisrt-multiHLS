import { Check, UploadCloud } from 'lucide-react'
import { ChangeEvent, FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { AgentTemplate, SourceLanguage, TargetLanguage, TranslationStyle } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { PageHeader } from '../components/PageHeader'
import { useCreateProject } from '../hooks/useApi'
import {
  AGENT_TEMPLATES,
  DUBBING_MODES,
  SOURCE_LANGUAGES,
  TARGET_LANGUAGES,
  TRANSLATION_STYLES,
} from '../lib/options'

const MAX_RECOMMENDED_BYTES = 500 * 1024 * 1024

export function UploadConfigPage() {
  const navigate = useNavigate()
  const createProject = useCreateProject()
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [sourceLanguage, setSourceLanguage] = useState<SourceLanguage>('auto')
  const [targetLanguages, setTargetLanguages] = useState<TargetLanguage[]>(['en-US'])
  const [translationStyle, setTranslationStyle] = useState<TranslationStyle>('short_drama_localized')
  const [dubbingMode, setDubbingMode] = useState<(typeof DUBBING_MODES)[number]['value']>('subtitle_only')
  const [agentTemplate, setAgentTemplate] = useState<AgentTemplate>('subtitle_draft')
  const [enableDiarization, setEnableDiarization] = useState(true)
  const [enableSourceSeparation, setEnableSourceSeparation] = useState(true)
  const [generatePreviewMp4, setGeneratePreviewMp4] = useState(false)
  const [ttsProvider, setTtsProvider] = useState('default')
  const [glossary, setGlossary] = useState('')
  const [submitError, setSubmitError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)
  const busy = createProject.isPending || submitting

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null
    setFile(selected)
    if (selected && !name) {
      setName(selected.name.replace(/\.[^.]+$/, ''))
    }
  }

  function toggleLanguage(language: TargetLanguage) {
    setTargetLanguages((current) => {
      if (current.includes(language)) {
        return current.length === 1 ? current : current.filter((item) => item !== language)
      }
      return [...current, language]
    })
  }

  function applyDubbingMode(mode: (typeof DUBBING_MODES)[number]['value']) {
    setDubbingMode(mode)
    if (mode === 'subtitle_only') {
      setAgentTemplate('subtitle_draft')
    } else {
      setAgentTemplate('full_dubbing')
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)

    if (!file) {
      setSubmitError(new Error('请选择 MP4 或 MOV 视频文件'))
      return
    }
    if (!/\.(mp4|mov)$/i.test(file.name)) {
      setSubmitError(new Error('MVP 优先支持 MP4/MOV'))
      return
    }
    if (!targetLanguages.length) {
      setSubmitError(new Error('至少选择一个目标语言'))
      return
    }

    try {
      setSubmitting(true)
      const created = await createProject.mutateAsync({
        name: name || file.name,
        source_language: sourceLanguage,
        target_languages: targetLanguages,
        translation_style: translationStyle,
      })
      await apiClient.uploadSourceVideo(created.upload_url, file)
      const run = await apiClient.processProject(created.project_id, {
        enable_source_separation: enableSourceSeparation,
        enable_diarization: enableDiarization,
        generate_tts: dubbingMode !== 'subtitle_only',
        generate_preview_mp4: generatePreviewMp4,
        agent_template: agentTemplate,
      })
      navigate(`/projects/${created.project_id}/progress?run_id=${run.run_id}`)
    } catch (error) {
      setSubmitError(error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="上传配置" description="创建项目、上传源视频并提交 Agent Run。" />

      <form className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]" onSubmit={handleSubmit}>
        <div className="panel">
          <div className="panel-header">
            <h2 className="text-base font-semibold">视频与语言</h2>
          </div>
          <div className="panel-body space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              <span className="mb-1 block">视频文件</span>
              <input
                className="block w-full rounded-md border border-line bg-white text-sm file:mr-3 file:h-9 file:border-0 file:bg-slate-100 file:px-3 file:text-sm file:font-medium"
                type="file"
                accept=".mp4,.mov,video/mp4,video/quicktime"
                onChange={handleFileChange}
              />
              {file && file.size > MAX_RECOMMENDED_BYTES ? (
                <span className="mt-1 block text-xs text-warn">文件超过 500MB，处理耗时可能明显增加。</span>
              ) : null}
            </label>

            <label className="block text-sm font-medium text-slate-700">
              <span className="mb-1 block">项目名称</span>
              <input className="field" value={name} onChange={(event) => setName(event.target.value)} />
            </label>

            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                <span className="mb-1 block">源语言</span>
                <select
                  className="field"
                  value={sourceLanguage}
                  onChange={(event) => setSourceLanguage(event.target.value as SourceLanguage)}
                >
                  {SOURCE_LANGUAGES.map((language) => (
                    <option key={language.value} value={language.value}>
                      {language.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm font-medium text-slate-700">
                <span className="mb-1 block">翻译风格</span>
                <select
                  className="field"
                  value={translationStyle}
                  onChange={(event) => setTranslationStyle(event.target.value as TranslationStyle)}
                >
                  {TRANSLATION_STYLES.map((style) => (
                    <option key={style.value} value={style.value}>
                      {style.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <fieldset>
              <legend className="mb-2 text-sm font-medium text-slate-700">目标语言</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {TARGET_LANGUAGES.map((language) => (
                  <label
                    key={language.value}
                    className="flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={targetLanguages.includes(language.value)}
                      onChange={() => toggleLanguage(language.value)}
                    />
                    {language.label}
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="block text-sm font-medium text-slate-700">
              <span className="mb-1 block">术语表或角色设定</span>
              <textarea
                className="textarea"
                value={glossary}
                onChange={(event) => setGlossary(event.target.value)}
                placeholder="人物名、固定译法、角色语气"
              />
            </label>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2 className="text-base font-semibold">处理选项</h2>
          </div>
          <div className="panel-body space-y-4">
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-slate-700">配音模式</legend>
              <div className="grid gap-2">
                {DUBBING_MODES.map((mode) => (
                  <label
                    key={mode.value}
                    className="flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm"
                  >
                    <input
                      type="radio"
                      checked={dubbingMode === mode.value}
                      onChange={() => applyDubbingMode(mode.value)}
                    />
                    {mode.label}
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="block text-sm font-medium text-slate-700">
              <span className="mb-1 block">处理模板</span>
              <select
                className="field"
                value={agentTemplate}
                onChange={(event) => setAgentTemplate(event.target.value as AgentTemplate)}
              >
                {AGENT_TEMPLATES.map((template) => (
                  <option key={template.value} value={template.value}>
                    {template.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-medium text-slate-700">
              <span className="mb-1 block">TTS 服务商</span>
              <select className="field" value={ttsProvider} onChange={(event) => setTtsProvider(event.target.value)}>
                <option value="default">默认</option>
                <option value="minimax">MiniMax</option>
                <option value="doubao">豆包</option>
                <option value="local">开源本地模型</option>
              </select>
            </label>

            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={enableDiarization}
                  onChange={(event) => setEnableDiarization(event.target.checked)}
                />
                启用说话人识别
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={enableSourceSeparation}
                  onChange={(event) => setEnableSourceSeparation(event.target.checked)}
                />
                启用人声分离
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={generatePreviewMp4}
                  onChange={(event) => setGeneratePreviewMp4(event.target.checked)}
                />
                生成 MP4 预览文件
              </label>
            </div>

            <ErrorNotice error={submitError} />

            <button className="btn btn-primary w-full" type="submit" disabled={busy}>
              {busy ? (
                <UploadCloud className="h-4 w-4 animate-pulse" aria-hidden="true" />
              ) : (
                <Check className="h-4 w-4" aria-hidden="true" />
              )}
              提交处理
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
