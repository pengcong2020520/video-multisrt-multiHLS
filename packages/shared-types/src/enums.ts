/**
 * Spec §5 任务状态机 + §4.2/§4.8/§7 衍生枚举。
 *
 * 枚举值与 Spec 文档逐字一致；新增值需先回 Spec 修订。
 */
import { z } from 'zod'
import { LanguageCodeSchema } from './languages.js'

/** Spec §5.1 Project Status。 */
export const ProjectStatusSchema = z.enum([
  'draft', // 已创建但未上传完成
  'uploaded', // 上传完成
  'planning', // Agent Runtime 正在生成执行计划
  'processing', // 自动处理中
  'proofreading', // 等待人工校对
  'generating', // 正在生成 TTS/混音/打包
  'completed', // 完成
  'failed', // 失败
  'archived', // 已归档
])
export type ProjectStatus = z.infer<typeof ProjectStatusSchema>

/** Spec §5.2 Task Status。 */
export const TaskStatusSchema = z.enum([
  'pending', // 等待执行
  'running', // 执行中
  'succeeded', // 成功
  'failed', // 失败
  'canceled', // 已取消
  'retrying', // 等待重试
])
export type TaskStatus = z.infer<typeof TaskStatusSchema>

/** Spec §5.3 Agent Run Status。 */
export const AgentRunStatusSchema = z.enum([
  'pending', // 等待开始
  'planning', // 生成执行计划
  'running', // 执行中
  'waiting_human', // 等待人工校对或确认
  'succeeded', // 成功
  'failed', // 失败
  'canceled', // 已取消
])
export type AgentRunStatus = z.infer<typeof AgentRunStatusSchema>

/** Spec §5.4 Task Type。 */
export const TaskTypeSchema = z.enum([
  'probe_media',
  'extract_audio',
  'separate_sources',
  'asr',
  'segment_normalize',
  'translate',
  'generate_subtitle',
  'tts',
  'stitch_target_vocal',
  'mix_audio',
  'package_outputs',
])
export type TaskType = z.infer<typeof TaskTypeSchema>

/** Spec §4.2 MediaAsset type。 */
export const AssetTypeSchema = z.enum([
  'source_video', // 原视频
  'source_audio', // 原始音频
  'source_vocal', // 分离后的原人声
  'background_audio', // 分离后的背景音
  'subtitle_srt', // SRT 字幕
  'subtitle_vtt', // WebVTT 字幕
  'tts_segment_audio', // 单句 TTS 音频
  'target_vocal', // 拼接后的目标语言人声
  'target_mix_audio', // 目标语言混合音轨
  'preview_video', // 预览 MP4
  'package_zip', // 下载包
])
export type AssetType = z.infer<typeof AssetTypeSchema>

/** Spec §4.8 AgentRun template。 */
export const AgentTemplateSchema = z.enum([
  'subtitle_draft', // 只生成 ASR、翻译和字幕初稿
  'full_dubbing', // 生成字幕、TTS、混音和下载包
  'rerun_segments', // 局部重跑指定句段
  'package_only', // 只重新生成 manifest 或下载包
])
export type AgentTemplate = z.infer<typeof AgentTemplateSchema>

/** Spec §7.8 generate scope。 */
export const GenerateScopeSchema = z.enum([
  'language', // 重跑整个目标语言
  'segments', // 只重跑指定句段
  'package', // 只重新打包
])
export type GenerateScope = z.infer<typeof GenerateScopeSchema>

/** Spec §7.8 generate steps。 */
export const GenerationStepSchema = z.enum(['subtitle', 'tts', 'mix'])
export type GenerationStep = z.infer<typeof GenerationStepSchema>

/** 字幕格式。 */
export const SubtitleFormatSchema = z.enum(['srt', 'vtt'])
export type SubtitleFormat = z.infer<typeof SubtitleFormatSchema>

/**
 * 句段级处理状态。Spec §4.4 Translation 与 §4.6 TTSJob 的 status 字段
 * 均出现 `completed`（区别于 TaskStatus 的 `succeeded`），故单独定义。
 */
export const ProcessingStatusSchema = z.enum(['pending', 'running', 'completed', 'failed'])
export type ProcessingStatus = z.infer<typeof ProcessingStatusSchema>

/** Spec §4.9 / §6 SkillRun / Skill 响应状态。 */
export const SkillRunStatusSchema = z.enum(['pending', 'running', 'succeeded', 'failed'])
export type SkillRunStatus = z.infer<typeof SkillRunStatusSchema>

/** 音轨语言：可为目标语言代码或字面量 `source`（原音轨）。 */
export const AudioTrackLanguageSchema = z.union([z.literal('source'), LanguageCodeSchema])
export type AudioTrackLanguage = z.infer<typeof AudioTrackLanguageSchema>
