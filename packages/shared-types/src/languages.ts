/**
 * Spec §3 语言代码
 *
 * 统一使用 BCP 47 风格语言代码。
 *
 * | 语言 | 代码 |
 * | --- | --- |
 * | 中文 | zh-CN |
 * | 英文 | en-US |
 * | 西语 | es-ES 或 es-MX |
 * | 葡语 | pt-BR |
 *
 * MVP 默认：
 * - 源语言：zh-CN、en-US、auto
 * - 目标语言：en-US、zh-CN、es-ES、pt-BR（auto 不可作为目标语言）
 */
import { z } from 'zod'

/** Spec §3 支持的具体语言代码（不含 auto）。 */
export const LanguageCodeSchema = z.enum(['zh-CN', 'en-US', 'es-ES', 'es-MX', 'pt-BR'])
export type LanguageCode = z.infer<typeof LanguageCodeSchema>

/** 源语言：具体语言代码或 `auto`（自动检测）。 */
export const SourceLanguageSchema = z.union([LanguageCodeSchema, z.literal('auto')])
export type SourceLanguage = z.infer<typeof SourceLanguageSchema>

/** 目标语言：只允许具体语言代码，不允许 `auto`。 */
export const TargetLanguageSchema = LanguageCodeSchema
export type TargetLanguage = z.infer<typeof TargetLanguageSchema>

/** 语言标签（manifest 中 source 音轨、字幕 label 等可读名称）。 */
export const LANGUAGE_LABELS: Readonly<Record<LanguageCode, string>> = {
  'zh-CN': '中文',
  'en-US': 'English',
  'es-ES': 'Español (España)',
  'es-MX': 'Español (México)',
  'pt-BR': 'Português (Brasil)',
}

/** MVP 默认可选源语言。 */
export const DEFAULT_SOURCE_LANGUAGES: readonly SourceLanguage[] = ['zh-CN', 'en-US', 'auto']
/** MVP 默认可选目标语言。 */
export const DEFAULT_TARGET_LANGUAGES: readonly TargetLanguage[] = ['en-US', 'zh-CN', 'es-ES', 'pt-BR']

/** 判断是否为合法目标语言。 */
export function isTargetLanguage(value: unknown): value is TargetLanguage {
  return TargetLanguageSchema.safeParse(value).success
}
