/**
 * Spec §12 错误码。
 *
 * 未知错误码必须被 Schema 拒绝（见 ErrorCodeSchema）。
 * 新增错误码需先回 Spec 修订。
 */
import { z } from 'zod'

export const ErrorCodeSchema = z.enum([
  'INVALID_VIDEO', // 视频格式或编码不支持
  'NO_AUDIO_TRACK', // 视频没有可用音轨
  'VIDEO_TOO_LONG', // 视频超出 MVP 时长限制
  'SOURCE_SEPARATION_FAILED', // 声源分离失败
  'ASR_FAILED', // ASR 失败
  'TRANSLATION_FAILED', // 翻译失败
  'TTS_FAILED', // TTS 失败
  'MIXING_FAILED', // 混音失败
  'PACKAGE_FAILED', // 打包失败
  'PROVIDER_RATE_LIMITED', // 模型供应商限流
  'PROVIDER_UNAVAILABLE', // 模型供应商不可用
  'AGENT_RUN_FAILED', // Agent Run 执行失败
  'SKILL_RUN_FAILED', // Skill Run 执行失败
  'HUMAN_CHECKPOINT_REQUIRED', // 需要人工确认后继续
])
export type ErrorCode = z.infer<typeof ErrorCodeSchema>

/** Spec §4.9 / §6 失败时记录的结构化错误。 */
export const SkillErrorSchema = z.object({
  code: ErrorCodeSchema,
  message: z.string().min(1),
})
export type SkillError = z.infer<typeof SkillErrorSchema>

/** Spec §5 task 失败记录的 error_code/error_message（task 表）。 */
export const TaskErrorSchema = z.object({
  code: ErrorCodeSchema,
  message: z.string().min(1),
})
export type TaskError = z.infer<typeof TaskErrorSchema>

/** 错误码说明（供前端展示）。 */
export const ERROR_CODE_MESSAGES: Readonly<Record<ErrorCode, string>> = {
  INVALID_VIDEO: '视频格式或编码不支持',
  NO_AUDIO_TRACK: '视频没有可用音轨',
  VIDEO_TOO_LONG: '视频超出 MVP 时长限制',
  SOURCE_SEPARATION_FAILED: '声源分离失败',
  ASR_FAILED: 'ASR 失败',
  TRANSLATION_FAILED: '翻译失败',
  TTS_FAILED: 'TTS 失败',
  MIXING_FAILED: '混音失败',
  PACKAGE_FAILED: '打包失败',
  PROVIDER_RATE_LIMITED: '模型供应商限流',
  PROVIDER_UNAVAILABLE: '模型供应商不可用',
  AGENT_RUN_FAILED: 'Agent Run 执行失败',
  SKILL_RUN_FAILED: 'Skill Run 执行失败',
  HUMAN_CHECKPOINT_REQUIRED: '需要人工确认后继续',
}
