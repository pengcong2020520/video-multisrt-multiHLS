/**
 * Skill-specific 输入/输出类型与 Schema（对应 docs/agent-skill-architecture.md §4 Skill 目录）。
 *
 * SkillDefinition.input_schema / output_schema 字段引用此处的类型名（如 "VoiceSynthesizeInput"）。
 */
import { z } from 'zod'
import {
  AssetTypeSchema,
  SubtitleFormatSchema,
} from './enums.js'
import { IdSchema, QualityFlagSchema } from './common.js'
import {
  ManifestSchema,
  SegmentSchema,
  SpeakerSchema,
} from './entities.js'
import {
  LanguageCodeSchema,
  SourceLanguageSchema,
  TargetLanguageSchema,
} from './languages.js'

// ─── media ───────────────────────────────────────────────────────────────────

export const MediaProbeInputSchema = z.object({
  source_video_asset_id: IdSchema,
})
export type MediaProbeInput = z.infer<typeof MediaProbeInputSchema>

export const MediaProbeOutputSchema = z.object({
  duration_ms: z.number().int().nonnegative(),
  container: z.string(), // 如 "mp4"
  has_audio: z.boolean(),
  video_codec: z.string().nullable(),
  audio_codec: z.string().nullable(),
  width: z.number().int().positive().nullable(),
  height: z.number().int().positive().nullable(),
  fps: z.number().positive().nullable(),
  size_bytes: z.number().int().nonnegative().nullable(),
})
export type MediaProbeOutput = z.infer<typeof MediaProbeOutputSchema>

export const MediaExtractAudioInputSchema = z.object({
  source_video_asset_id: IdSchema,
  format: z.string().default('wav'), // 提取音频格式
})
export type MediaExtractAudioInput = z.infer<typeof MediaExtractAudioInputSchema>

export const MediaExtractAudioOutputSchema = z.object({
  audio_asset_id: IdSchema,
  duration_ms: z.number().int().nonnegative(),
})
export type MediaExtractAudioOutput = z.infer<typeof MediaExtractAudioOutputSchema>

export const AudioSeparateSourcesInputSchema = z.object({
  audio_asset_id: IdSchema,
  mode: z.enum(['vocal_background']),
})
export type AudioSeparateSourcesInput = z.infer<typeof AudioSeparateSourcesInputSchema>

export const AudioSeparateSourcesOutputSchema = z.object({
  source_vocal_asset_id: IdSchema,
  background_asset_id: IdSchema,
  quality_score: z.union([z.number().min(0).max(1), z.null()]),
})
export type AudioSeparateSourcesOutput = z.infer<typeof AudioSeparateSourcesOutputSchema>

// ─── asr ─────────────────────────────────────────────────────────────────────

export const AsrTranscribeInputSchema = z.object({
  audio_asset_id: IdSchema,
  source_language: SourceLanguageSchema,
  enable_diarization: z.boolean().default(false),
})
export type AsrTranscribeInput = z.infer<typeof AsrTranscribeInputSchema>

/** ASR 原始片段（尚未归一化为 Segment）。 */
export const RawTranscriptSegmentSchema = z.object({
  start_ms: z.number().int().nonnegative(),
  end_ms: z.number().int().nonnegative(),
  text: z.string(),
  speaker_id: z.string().nullable().optional(),
  confidence: z.union([z.number().min(0).max(1), z.null()]).optional(),
})
export type RawTranscriptSegment = z.infer<typeof RawTranscriptSegmentSchema>

export const AsrTranscribeOutputSchema = z.object({
  detected_language: z.union([LanguageCodeSchema, z.null()]),
  raw_segments: z.array(RawTranscriptSegmentSchema),
})
export type AsrTranscribeOutput = z.infer<typeof AsrTranscribeOutputSchema>

export const AsrDiarizeInputSchema = z.object({
  audio_asset_id: IdSchema,
})
export type AsrDiarizeInput = z.infer<typeof AsrDiarizeInputSchema>

export const AsrDiarizeOutputSchema = z.object({
  speakers: z.array(SpeakerSchema),
})
export type AsrDiarizeOutput = z.infer<typeof AsrDiarizeOutputSchema>

export const TranscriptNormalizeSegmentsInputSchema = z.object({
  raw_segments: z.array(RawTranscriptSegmentSchema),
  source_language: SourceLanguageSchema,
})
export type TranscriptNormalizeSegmentsInput = z.infer<
  typeof TranscriptNormalizeSegmentsInputSchema
>

export const TranscriptNormalizeSegmentsOutputSchema = z.object({
  segments: z.array(SegmentSchema),
})
export type TranscriptNormalizeSegmentsOutput = z.infer<
  typeof TranscriptNormalizeSegmentsOutputSchema
>

// ─── localization ────────────────────────────────────────────────────────────

export const LocalizationTranslateInputSchema = z.object({
  source_language: LanguageCodeSchema,
  target_language: TargetLanguageSchema,
  segments: z.array(SegmentSchema),
  style: z.string(),
  glossary: z.record(z.string(), z.string()).default({}),
  character_notes: z.array(z.string()).default([]),
})
export type LocalizationTranslateInput = z.infer<typeof LocalizationTranslateInputSchema>

export const LocalizationTranslationItemSchema = z.object({
  segment_id: IdSchema,
  text: z.string(),
  quality_flags: z.array(QualityFlagSchema),
})
export type LocalizationTranslationItem = z.infer<typeof LocalizationTranslationItemSchema>

export const LocalizationTranslateOutputSchema = z.object({
  translations: z.array(LocalizationTranslationItemSchema),
  model: z.string(),
  prompt_version: z.string(),
})
export type LocalizationTranslateOutput = z.infer<typeof LocalizationTranslateOutputSchema>

// ─── voice ───────────────────────────────────────────────────────────────────

export const VoiceSynthesizeInputSchema = z.object({
  target_language: TargetLanguageSchema,
  text: z.string(),
  voice_id: z.string().min(1),
  target_duration_ms: z.union([z.number().int().nonnegative(), z.null()]),
  speed: z.number().positive().default(1.0),
  style: z.string().optional(),
})
export type VoiceSynthesizeInput = z.infer<typeof VoiceSynthesizeInputSchema>

export const VoiceSynthesizeOutputSchema = z.object({
  audio_asset_id: IdSchema,
  actual_duration_ms: z.number().int().nonnegative(),
  provider: z.string(),
  provider_task_id: z.string().nullable(),
})
export type VoiceSynthesizeOutput = z.infer<typeof VoiceSynthesizeOutputSchema>

// ─── packaging ───────────────────────────────────────────────────────────────

export const SubtitleGenerateInputSchema = z.object({
  segments: z.array(SegmentSchema),
  translations: z.array(
    z.object({
      segment_id: IdSchema,
      target_language: TargetLanguageSchema,
      text: z.string(),
    }),
  ),
  target_languages: z.array(TargetLanguageSchema),
  format: SubtitleFormatSchema,
})
export type SubtitleGenerateInput = z.infer<typeof SubtitleGenerateInputSchema>

export const SubtitleGenerateOutputSchema = z.object({
  assets: z.array(
    z.object({
      language: LanguageCodeSchema,
      format: SubtitleFormatSchema,
      asset_id: IdSchema,
    }),
  ),
})
export type SubtitleGenerateOutput = z.infer<typeof SubtitleGenerateOutputSchema>

export const AudioStitchVocalsInputSchema = z.object({
  tts_asset_ids: z.array(IdSchema),
  segments: z.array(SegmentSchema),
  target_language: TargetLanguageSchema,
})
export type AudioStitchVocalsInput = z.infer<typeof AudioStitchVocalsInputSchema>

export const AudioStitchVocalsOutputSchema = z.object({
  target_vocal_asset_id: IdSchema,
})
export type AudioStitchVocalsOutput = z.infer<typeof AudioStitchVocalsOutputSchema>

export const AudioMixInputSchema = z.object({
  target_vocal_asset_id: IdSchema,
  background_asset_id: IdSchema,
  target_language: TargetLanguageSchema,
})
export type AudioMixInput = z.infer<typeof AudioMixInputSchema>

export const AudioMixOutputSchema = z.object({
  target_mix_asset_id: IdSchema,
})
export type AudioMixOutput = z.infer<typeof AudioMixOutputSchema>

export const PackageManifestInputSchema = z.object({
  project_id: IdSchema,
  version_id: IdSchema,
})
export type PackageManifestInput = z.infer<typeof PackageManifestInputSchema>

export const PackageManifestOutputSchema = z.object({
  manifest: ManifestSchema,
})
export type PackageManifestOutput = z.infer<typeof PackageManifestOutputSchema>

export const PackageZipInputSchema = z.object({
  project_id: IdSchema,
  version_id: IdSchema,
  languages: z.array(TargetLanguageSchema),
  include_intermediate_assets: z.boolean().default(false),
})
export type PackageZipInput = z.infer<typeof PackageZipInputSchema>

export const PackageZipOutputSchema = z.object({
  package_asset_id: IdSchema,
  type: z.literal(AssetTypeSchema.enum.package_zip),
})
export type PackageZipOutput = z.infer<typeof PackageZipOutputSchema>
