import { Check, UploadCloud } from 'lucide-react'
import { ChangeEvent, FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { SourceLanguage } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { PageHeader } from '../components/PageHeader'
import { useCreateProject } from '../hooks/useApi'
import { SOURCE_LANGUAGES } from '../lib/options'

const MAX_RECOMMENDED_BYTES = 500 * 1024 * 1024

export function UploadConfigPage() {
  const navigate = useNavigate()
  const createProject = useCreateProject()
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [sourceLanguage, setSourceLanguage] = useState<SourceLanguage>('auto')
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

    try {
      setSubmitting(true)
      const created = await createProject.mutateAsync({
        name: name || file.name,
        source_language: sourceLanguage,
      })
      await apiClient.uploadSourceVideo(created.upload_url, file)
      navigate(`/projects/${created.project_id}/preview`)
    } catch (error) {
      setSubmitError(error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="上传视频" description="选择源语言并上传，随后进入预览页处理字幕和配音。" />

      <form className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]" onSubmit={handleSubmit}>
        <div className="panel">
          <div className="panel-header">
            <h2 className="text-base font-semibold">视频与源语言</h2>
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
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2 className="text-base font-semibold">提交</h2>
          </div>
          <div className="panel-body space-y-3">
            <ErrorNotice error={submitError} />

            <button className="btn btn-primary w-full" type="submit" disabled={busy}>
              {busy ? (
                <UploadCloud className="h-4 w-4 animate-pulse" aria-hidden="true" />
              ) : (
                <Check className="h-4 w-4" aria-hidden="true" />
              )}
              上传并预览
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
