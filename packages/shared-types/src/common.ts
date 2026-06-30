/**
 * 跨实体复用的公共类型与 Schema。
 */
import { z } from 'zod'
import { AssetTypeSchema } from './enums.js'
import { LanguageCodeSchema, SourceLanguageSchema } from './languages.js'

/** ISO 8601 时间戳（UTC，如 `2026-06-30T10:00:00Z`）。 */
export const IsoTimestampSchema = z.string().datetime({ offset: false })
export type IsoTimestamp = z.infer<typeof IsoTimestampSchema>

/** 资源标识符（asset/run/segment 等业务 ID，非空字符串）。 */
export const IdSchema = z.string().min(1)

/**
 * Spec §6 / §9 质量提示。可附加在 segment、translation、TTS、skill run 上。
 * `code` 为机器可读标识（如 `too_long`、`duration_drift`），其余字段可选。
 */
export const QualityFlagSchema = z.object({
  code: z.string().min(1),
  message: z.string().optional(),
  severity: z.enum(['info', 'warning', 'error']).optional(),
  segment_id: IdSchema.optional(),
  language: LanguageCodeSchema.optional(),
})
export type QualityFlag = z.infer<typeof QualityFlagSchema>

/** Spec §6 Skill 输出中的资产引用（只记引用，不嵌大型内容）。 */
export const SkillAssetRefSchema = z.object({
  asset_id: IdSchema,
  type: AssetTypeSchema.optional(),
  language: z.union([SourceLanguageSchema, z.null()]).optional(),
  uri: z.string().optional(),
})
export type SkillAssetRef = z.infer<typeof SkillAssetRefSchema>

/** Spec §6 Skill usage（计费/模型用量）。失败时可为空对象。 */
export const SkillUsageSchema = z.object({
  provider: z.string().optional(),
  model: z.string().optional(),
  tokens: z.number().int().nonnegative().optional(),
  cost: z.union([z.number(), z.null()]).optional(),
})
export type SkillUsage = z.infer<typeof SkillUsageSchema>

/** 空的 usage（失败响应默认值）。 */
export const EMPTY_USAGE: SkillUsage = {}
