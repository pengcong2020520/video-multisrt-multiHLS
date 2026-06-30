/**
 * Spec §11 模型适配器接口类型与 Schema。
 *
 * Adapter 是 Skill provider 与具体模型/服务之间的适配层。
 * 与 skill-io.ts 的区别：Adapter 关注「调用一次外部模型」的输入输出，
 * 不含 skill_name/project_id/run_id 等编排信封字段。
 */
import { z } from 'zod'
import { IdSchema, QualityFlagSchema } from './common.js'
import {
  LanguageCodeSchema,
  SourceLanguageSchema,
  TargetLanguageSchema,
} from './languages.js'
import { SegmentSchema } from './entities.js'

// ─── §11.1 ASR Adapter ───────────────────────────────────────────────────────

export const AsrAdapterInputSchema = z.object({
  audio_asset_id: IdSchema,
  source_language: SourceLanguageSchema,
  enable_diarization: z.boolean(),
})
export type AsrAdapterInput = z.infer<typeof AsrAdapterInputSchema>

export const AsrAdapterOutputSchema = z.object({
  detected_language: z.union([LanguageCodeSchema, z.null()]),
  segments: z.array(SegmentSchema),
})
export type AsrAdapterOutput = z.infer<typeof AsrAdapterOutputSchema>

// ─── §11.2 Translation Adapter ───────────────────────────────────────────────

export const TranslationAdapterInputSchema = z.object({
  source_language: LanguageCodeSchema,
  target_language: TargetLanguageSchema,
  segments: z.array(SegmentSchema),
  style: z.string(),
  glossary: z.record(z.string(), z.string()),
  character_notes: z.array(z.string()),
})
export type TranslationAdapterInput = z.infer<typeof TranslationAdapterInputSchema>

export const TranslationAdapterOutputSchema = z.object({
  translations: z.array(
    z.object({
      segment_id: IdSchema,
      text: z.string(),
      quality_flags: z.array(QualityFlagSchema),
    }),
  ),
  model: z.string(),
  prompt_version: z.string(),
})
export type TranslationAdapterOutput = z.infer<typeof TranslationAdapterOutputSchema>

// ─── §11.3 TTS Adapter ───────────────────────────────────────────────────────

export const TtsAdapterInputSchema = z.object({
  target_language: TargetLanguageSchema,
  text: z.string(),
  voice_id: z.string().min(1),
  target_duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
  speed: z.number().positive(),
  style: z.string().optional(),
})
export type TtsAdapterInput = z.infer<typeof TtsAdapterInputSchema>

export const TtsAdapterOutputSchema = z.object({
  audio_asset_id: IdSchema,
  actual_duration_ms: z.number().int().nonnegative(),
  provider: z.string(),
  provider_task_id: z.string(),
})
export type TtsAdapterOutput = z.infer<typeof TtsAdapterOutputSchema>

// ─── §11.4 Source Separation Adapter ─────────────────────────────────────────

export const SourceSeparationAdapterInputSchema = z.object({
  audio_asset_id: IdSchema,
  mode: z.enum(['vocal_background']),
})
export type SourceSeparationAdapterInput = z.infer<typeof SourceSeparationAdapterInputSchema>

export const SourceSeparationAdapterOutputSchema = z.object({
  source_vocal_asset_id: IdSchema,
  background_asset_id: IdSchema,
  quality_score: z.union([z.number().min(0).max(1), z.null()]),
})
export type SourceSeparationAdapterOutput = z.infer<typeof SourceSeparationAdapterOutputSchema>
