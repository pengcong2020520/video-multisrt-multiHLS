import type { AgentTemplate, SourceLanguage, TargetLanguage, TranslationStyle } from '../api/types'

export const SOURCE_LANGUAGES: Array<{ value: SourceLanguage; label: string }> = [
  { value: 'auto', label: '自动识别' },
  { value: 'zh-CN', label: '中文' },
  { value: 'en-US', label: 'English' },
]

export const TARGET_LANGUAGES: Array<{ value: TargetLanguage; label: string }> = [
  { value: 'en-US', label: 'English' },
  { value: 'es-ES', label: 'Español' },
  { value: 'pt-BR', label: 'Português' },
  { value: 'zh-CN', label: '中文' },
]

export const TRANSLATION_STYLES: Array<{ value: TranslationStyle; label: string }> = [
  { value: 'short_drama_localized', label: '短剧口语化' },
  { value: 'high_emotion', label: '强情绪' },
  { value: 'platform_natural', label: '平台自然口吻' },
]

export const DUBBING_MODES = [
  { value: 'default_voice', label: '默认音色' },
  { value: 'speaker_voice', label: '按角色分配音色' },
  { value: 'subtitle_only', label: '暂不生成配音' },
] as const

export const AGENT_TEMPLATES: Array<{ value: AgentTemplate; label: string }> = [
  { value: 'subtitle_draft', label: '仅字幕' },
  { value: 'full_dubbing', label: '字幕加配音' },
  { value: 'package_only', label: '完整混音打包' },
]

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: '已创建',
  uploaded: '已上传',
  planning: '规划中',
  processing: '处理中',
  proofreading: '待校对',
  generating: '生成中',
  completed: '完成',
  failed: '失败',
  archived: '已归档',
}

export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: '等待',
  running: '执行中',
  succeeded: '成功',
  failed: '失败',
  canceled: '取消',
  retrying: '重试中',
  completed: '完成',
}

export const STAGE_LABELS: Record<string, string> = {
  uploaded: '文件已上传',
  planning: '生成执行计划',
  probing: '解析视频',
  'media.probe': '解析视频',
  extracting_audio: '提取音频',
  'media.extract_audio': '提取音频',
  separating_sources: '分离人声和背景音',
  'audio.separate_sources': '分离人声和背景音',
  transcribing: '识别原语言台词',
  'asr.transcribe': '识别原语言台词',
  'asr.diarize': '识别说话人',
  segmenting: '分句和修正时间轴',
  'transcript.normalize_segments': '分句和修正时间轴',
  translating: '生成目标语言译文',
  'localization.translate': '生成目标语言译文',
  proofreading: '等待人工校对',
  'pause_for_proofreading': '等待人工校对',
  synthesizing: '生成目标语言人声',
  'voice.synthesize': '生成目标语言人声',
  'audio.stitch_vocals': '拼接目标语言人声',
  mixing: '混合目标语言音轨',
  'audio.mix': '混合目标语言音轨',
  packaging: '生成预览和下载包',
  'package.manifest': '生成 manifest',
  'package.zip': '生成下载包',
  completed: '处理完成',
  failed: '处理失败',
}

export function languageLabel(language: string | null | undefined): string {
  if (!language) {
    return '-'
  }
  return (
    TARGET_LANGUAGES.find((item) => item.value === language)?.label ||
    SOURCE_LANGUAGES.find((item) => item.value === language)?.label ||
    (language === 'source' ? '原音轨' : language)
  )
}
