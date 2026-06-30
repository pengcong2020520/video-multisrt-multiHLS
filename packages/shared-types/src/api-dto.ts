/**
 * Spec §7 最小 API DTO（Request/Response）。
 *
 * 仅定义语义与字段，不绑定具体框架。供 apps/web 与 apps/api 共用。
 */
import { z } from 'zod'
import {
  AgentTemplateSchema,
  GenerateScopeSchema,
  GenerationStepSchema,
} from './enums.js'
import { IdSchema, QualityFlagSchema } from './common.js'
import {
  AgentRunSchema,
  MediaAssetSchema,
  ProjectSchema,
  SegmentSchema,
  SkillRunSchema,
  TaskSchema,
  TTSJobSchema,
  TranslationSchema,
} from './entities.js'
import { ManifestSchema } from './entities.js'
import {
  SourceLanguageSchema,
  TargetLanguageSchema,
} from './languages.js'

// ─── §7.1 创建项目 ───────────────────────────────────────────────────────────

export const CreateProjectRequestSchema = z.object({
  name: z.string().min(1),
  source_language: SourceLanguageSchema,
  target_languages: z.array(TargetLanguageSchema).min(1),
  translation_style: z.string(),
})
export type CreateProjectRequest = z.infer<typeof CreateProjectRequestSchema>

export const CreateProjectResponseSchema = z.object({
  project_id: IdSchema,
  upload_url: z.string().url(),
})
export type CreateProjectResponse = z.infer<typeof CreateProjectResponseSchema>

// ─── §7.2 提交处理 ───────────────────────────────────────────────────────────

export const ProcessProjectRequestSchema = z.object({
  enable_source_separation: z.boolean(),
  enable_diarization: z.boolean(),
  generate_tts: z.boolean(),
  generate_preview_mp4: z.boolean(),
  agent_template: AgentTemplateSchema,
})
export type ProcessProjectRequest = z.infer<typeof ProcessProjectRequestSchema>

export const ProcessProjectResponseSchema = z.object({
  run_id: IdSchema,
  status: z.enum(['pending', 'planning', 'running']),
})
export type ProcessProjectResponse = z.infer<typeof ProcessProjectResponseSchema>

// ─── §7.3 查询 Agent Run ─────────────────────────────────────────────────────

export const GetAgentRunResponseSchema = z.object({
  agent_run: AgentRunSchema,
  skill_runs: z.array(SkillRunSchema),
  current_checkpoint: z.union([z.string(), z.null()]),
  quality_flags: z.array(QualityFlagSchema),
})
export type GetAgentRunResponse = z.infer<typeof GetAgentRunResponseSchema>

// ─── §7.4 继续 Agent Run ─────────────────────────────────────────────────────

export const ContinueAgentRunRequestSchema = z.object({
  checkpoint: z.string().min(1), // 如 "proofreading"
  confirmed: z.boolean(),
})
export type ContinueAgentRunRequest = z.infer<typeof ContinueAgentRunRequestSchema>

// ─── §7.5 查询项目详情 ───────────────────────────────────────────────────────

export const GetProjectResponseSchema = z.object({
  project: ProjectSchema,
  tasks: z.array(TaskSchema),
  assets: z.array(MediaAssetSchema),
  languages: z.array(TargetLanguageSchema),
})
export type GetProjectResponse = z.infer<typeof GetProjectResponseSchema>

// ─── §7.6 查询句段 ───────────────────────────────────────────────────────────

export const SegmentBundleSchema = z.object({
  segment: SegmentSchema,
  translation: z.union([TranslationSchema, z.null()]),
  tts_job: z.union([TTSJobSchema, z.null()]),
})
export type SegmentBundle = z.infer<typeof SegmentBundleSchema>

export const GetSegmentsResponseSchema = z.object({
  segments: z.array(SegmentBundleSchema),
})
export type GetSegmentsResponse = z.infer<typeof GetSegmentsResponseSchema>

// ─── §7.7 更新句段和译文 ─────────────────────────────────────────────────────

export const PatchSegmentRequestSchema = z
  .object({
    start_ms: z.number().int().nonnegative().optional(),
    end_ms: z.number().int().nonnegative().optional(),
    speaker_id: z.union([IdSchema, z.null()]).optional(),
    translations: z.record(TargetLanguageSchema, z.string()).optional(),
    locked: z.boolean().optional(),
  })
  .refine((d) => (d.start_ms == null || d.end_ms == null ? true : d.start_ms < d.end_ms), {
    message: 'start_ms must be less than end_ms',
    path: ['start_ms'],
  })
export type PatchSegmentRequest = z.infer<typeof PatchSegmentRequestSchema>

// ─── §7.8 生成或重跑目标语言 ─────────────────────────────────────────────────

export const GenerateProjectRequestSchema = z.object({
  target_language: TargetLanguageSchema,
  scope: GenerateScopeSchema,
  steps: z.array(GenerationStepSchema),
  segment_ids: z.array(IdSchema),
  agent_template: AgentTemplateSchema,
})
export type GenerateProjectRequest = z.infer<typeof GenerateProjectRequestSchema>

// ─── §7.9 获取播放器 Manifest ────────────────────────────────────────────────

export const ManifestResponseSchema = ManifestSchema
export type ManifestResponse = z.infer<typeof ManifestResponseSchema>

// ─── §7.10 下载结果包 ────────────────────────────────────────────────────────

export const CreatePackageRequestSchema = z.object({
  version_id: IdSchema,
  languages: z.array(TargetLanguageSchema),
  include_intermediate_assets: z.boolean(),
})
export type CreatePackageRequest = z.infer<typeof CreatePackageRequestSchema>

export const CreatePackageResponseSchema = z.object({
  package_id: IdSchema,
  status: z.enum(['pending', 'running', 'succeeded', 'failed']),
})
export type CreatePackageResponse = z.infer<typeof CreatePackageResponseSchema>
