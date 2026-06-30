/**
 * Spec §4 核心实体（含运行时 zod Schema）+ 支撑表（tasks/versions/audit_logs）。
 *
 * 规则：
 * - Segment.start_ms 必须小于 end_ms（Spec §4.3）。
 * - locked=true 的 segment 不允许被自动重写（Spec §4.3、§6）——语义由 Runtime 强制，此处仅固化字段。
 * - 同一 segment + target_language 可有多个版本，但只能有一个 active=true（Spec §4.4）。
 */
import { z } from 'zod'
import {
  AgentRunStatusSchema,
  AgentTemplateSchema,
  AssetTypeSchema,
  AudioTrackLanguageSchema,
  ProcessingStatusSchema,
  ProjectStatusSchema,
  SkillRunStatusSchema,
  SubtitleFormatSchema,
  TaskStatusSchema,
  TaskTypeSchema,
} from './enums.js'
import { ErrorCodeSchema } from './errors.js'
import { IdSchema, IsoTimestampSchema, QualityFlagSchema } from './common.js'
import {
  LanguageCodeSchema,
  SourceLanguageSchema,
  TargetLanguageSchema,
} from './languages.js'

/** Spec §4.1 Project。 */
export const ProjectSchema = z.object({
  project_id: IdSchema,
  name: z.string().min(1),
  status: ProjectStatusSchema,
  source_language: SourceLanguageSchema,
  target_languages: z.array(TargetLanguageSchema),
  duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
  created_by: IdSchema,
  created_at: IsoTimestampSchema,
  updated_at: IsoTimestampSchema,
})
export type Project = z.infer<typeof ProjectSchema>

/** Spec §4.2 MediaAsset。 */
export const MediaAssetSchema = z.object({
  asset_id: IdSchema,
  project_id: IdSchema,
  type: AssetTypeSchema,
  language: z.union([SourceLanguageSchema, z.null()]),
  uri: z.string().min(1),
  format: z.string().min(1),
  duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
  size_bytes: z.union([z.number().int().nonnegative(), z.null()]),
  checksum: z.string().optional(),
  created_at: IsoTimestampSchema,
})
export type MediaAsset = z.infer<typeof MediaAssetSchema>

/** Spec §4.3 Segment —— 字幕、翻译和 TTS 的共同最小单位。 */
export const SegmentSchema = z
  .object({
    segment_id: IdSchema,
    project_id: IdSchema,
    index: z.number().int().nonnegative(),
    start_ms: z.number().int().nonnegative(),
    end_ms: z.number().int().nonnegative(),
    speaker_id: z.union([IdSchema, z.null()]),
    source_language: SourceLanguageSchema,
    source_text: z.string(),
    asr_confidence: z.union([z.number().min(0).max(1), z.null()]),
    locked: z.boolean(),
    quality_flags: z.array(QualityFlagSchema),
    // 扩展字段（Spec §4.3：人工编辑后的 segment 需要记录版本）
    version: z.string().optional(),
  })
  .refine((s) => s.start_ms < s.end_ms, {
    message: 'start_ms must be less than end_ms',
    path: ['start_ms'],
  })
export type Segment = z.infer<typeof SegmentSchema>

/** Spec §4.4 Translation。 */
export const TranslationSchema = z.object({
  translation_id: IdSchema,
  segment_id: IdSchema,
  target_language: TargetLanguageSchema,
  text: z.string(),
  style: z.string(),
  model: z.string().optional(),
  prompt_version: z.string().optional(),
  status: ProcessingStatusSchema,
  edited_by: z.union([IdSchema, z.null()]),
  updated_at: IsoTimestampSchema,
  // 扩展字段（Spec §4.4：同一 segment+target_language 只能有一个 active=true）
  active: z.boolean().optional(),
  version: z.string().optional(),
})
export type Translation = z.infer<typeof TranslationSchema>

/** Spec §4.5 Speaker。 */
export const SpeakerSchema = z.object({
  speaker_id: IdSchema,
  project_id: IdSchema,
  display_name: z.string().min(1),
  source_voice_sample_asset_id: z.union([IdSchema, z.null()]),
  target_voice_map: z.record(TargetLanguageSchema, IdSchema),
})
export type Speaker = z.infer<typeof SpeakerSchema>

/** Spec §4.6 TTSJob。 */
export const TTSJobSchema = z.object({
  tts_job_id: IdSchema,
  project_id: IdSchema,
  segment_id: IdSchema,
  target_language: TargetLanguageSchema,
  text: z.string(),
  voice_id: z.string().min(1),
  target_duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
  speed: z.number().positive(),
  status: ProcessingStatusSchema,
  output_asset_id: z.union([IdSchema, z.null()]),
  actual_duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
  provider: z.string().optional(),
  provider_task_id: z.union([z.string(), z.null()]).optional(),
  error: z
    .object({
      code: ErrorCodeSchema,
      message: z.string().min(1),
    })
    .nullable(),
  quality_flags: z.array(QualityFlagSchema).optional(),
})
export type TTSJob = z.infer<typeof TTSJobSchema>

/** Spec §4.7 Manifest —— 网页播放器可播放资源描述。 */
export const ManifestVideoSchema = z.object({
  url: z.string().min(1),
  duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
})
export type ManifestVideo = z.infer<typeof ManifestVideoSchema>

export const ManifestSubtitleSchema = z.object({
  language: z.union([z.literal('source'), LanguageCodeSchema]),
  label: z.string().min(1),
  format: SubtitleFormatSchema,
  url: z.string().min(1),
})
export type ManifestSubtitle = z.infer<typeof ManifestSubtitleSchema>

export const ManifestAudioTrackSchema = z.object({
  language: AudioTrackLanguageSchema,
  label: z.string().min(1),
  url: z.string().min(1),
})
export type ManifestAudioTrack = z.infer<typeof ManifestAudioTrackSchema>

export const ManifestDownloadSchema = z.object({
  type: AssetTypeSchema,
  label: z.string().min(1),
  url: z.string().min(1),
})
export type ManifestDownload = z.infer<typeof ManifestDownloadSchema>

export const ManifestSchema = z.object({
  project_id: IdSchema,
  version_id: IdSchema,
  video: ManifestVideoSchema,
  subtitles: z.array(ManifestSubtitleSchema),
  audio_tracks: z.array(ManifestAudioTrackSchema),
  downloads: z.array(ManifestDownloadSchema),
})
export type Manifest = z.infer<typeof ManifestSchema>

/** Spec §4.8 AgentRun。 */
export const AgentRunSchema = z.object({
  run_id: IdSchema,
  project_id: IdSchema,
  version_id: z.union([IdSchema, z.null()]),
  template: AgentTemplateSchema,
  status: AgentRunStatusSchema,
  current_step: z.union([z.string(), z.null()]),
  source_language: SourceLanguageSchema,
  target_languages: z.array(TargetLanguageSchema),
  created_by: IdSchema,
  created_at: IsoTimestampSchema,
  updated_at: IsoTimestampSchema,
})
export type AgentRun = z.infer<typeof AgentRunSchema>

/** Spec §4.9 SkillRun。 */
export const SkillRunSchema = z.object({
  skill_run_id: IdSchema,
  run_id: IdSchema,
  project_id: IdSchema,
  skill_name: z.string().min(1),
  skill_version: z.string().min(1),
  status: SkillRunStatusSchema,
  target_language: z.union([TargetLanguageSchema, z.null()]),
  started_at: IsoTimestampSchema,
  finished_at: z.union([IsoTimestampSchema, z.null()]),
  input_refs: z.array(IdSchema),
  output_refs: z.array(IdSchema),
  provider: z.union([z.string(), z.null()]),
  model: z.union([z.string(), z.null()]),
  error: z
    .object({
      code: ErrorCodeSchema,
      message: z.string().min(1),
    })
    .nullable(),
})
export type SkillRun = z.infer<typeof SkillRunSchema>

/** Spec §4.10 SkillDefinition（前端只能查看可展示字段，不能读取 API key）。 */
export const SkillDefinitionSchema = z.object({
  skill_name: z.string().min(1),
  skill_version: z.string().min(1),
  enabled: z.boolean(),
  default_provider: z.union([z.string(), z.null()]),
  input_schema: z.string().min(1), // 输入类型名（如 "VoiceSynthesizeInput"）
  output_schema: z.string().min(1), // 输出类型名（如 "VoiceSynthesizeOutput"）
  timeout_seconds: z.number().int().positive(),
  retry_limit: z.number().int().nonnegative(),
})
export type SkillDefinition = z.infer<typeof SkillDefinitionSchema>

// ────────────────────────────────────────────────────────────────────────────
// 支撑表（任务卡要求提供类型/Schema：tasks / versions / audit_logs）
// ────────────────────────────────────────────────────────────────────────────

/** Spec §5 task 行（每个 task 绑定 project_id；编排型绑定 run_id；语言型绑定 target_language）。 */
export const TaskSchema = z.object({
  task_id: IdSchema,
  project_id: IdSchema,
  run_id: z.union([IdSchema, z.null()]),
  task_type: TaskTypeSchema,
  target_language: z.union([TargetLanguageSchema, z.null()]),
  status: TaskStatusSchema,
  error_code: z.union([ErrorCodeSchema, z.null()]),
  error_message: z.union([z.string(), z.null()]),
  retry_count: z.number().int().nonnegative(),
  created_at: IsoTimestampSchema,
  updated_at: IsoTimestampSchema,
})
export type Task = z.infer<typeof TaskSchema>

/** versions 表 —— 项目产物版本（manifest/打包以 version_id 为锚）。 */
export const VersionSchema = z.object({
  version_id: IdSchema,
  project_id: IdSchema,
  is_active: z.boolean(),
  label: z.union([z.string(), z.null()]),
  created_by: IdSchema,
  created_at: IsoTimestampSchema,
})
export type Version = z.infer<typeof VersionSchema>

/** audit_logs 表 —— Spec §13 操作日志（上传、编辑、生成、下载行为）。 */
export const AuditLogSchema = z.object({
  log_id: IdSchema,
  project_id: IdSchema,
  actor: IdSchema,
  action: z.string().min(1), // upload | edit | generate | download | ...
  target_type: z.string().optional(),
  target_id: z.union([IdSchema, z.null()]).optional(),
  detail: z.record(z.string(), z.unknown()).optional(),
  created_at: IsoTimestampSchema,
})
export type AuditLog = z.infer<typeof AuditLogSchema>
