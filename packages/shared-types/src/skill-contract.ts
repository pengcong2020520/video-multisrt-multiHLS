/**
 * Spec §6 Skill 调用契约。
 *
 * Skill 是 Agent Runtime 的最小可复用能力单元，统一使用结构化输入输出。
 * - Skill 不直接决定下一步流程（由 Agent Runtime 决定）。
 * - Skill 不删除上游资产，不能覆盖 locked segment。
 * - Skill 所需密钥由服务端注入，不能由前端传入。
 *
 * 这里同时提供泛型 TS 类型（供 Skill provider 实现强类型）和
 * 通用 zod Schema（供 Runtime 做结构校验，input/output 载荷由具体 Skill 的 IO Schema 校验）。
 */
import { z } from 'zod'
import {
  EMPTY_USAGE,
  IdSchema,
  type QualityFlag,
  QualityFlagSchema,
  type SkillAssetRef,
  SkillAssetRefSchema,
  SkillUsageSchema,
} from './common.js'
import { SkillRunStatusSchema } from './enums.js'
import { SkillErrorSchema } from './errors.js'

/** Spec §6 Skill Request（泛型：TInput 为 Skill 输入，TConfig 为运行配置）。 */
export interface SkillRequest<TInput = unknown, TConfig = Record<string, unknown>> {
  skill_name: string
  skill_version: string
  project_id: string
  run_id: string
  input: TInput
  config: TConfig
  idempotency_key: string
}

/** Spec §6 Skill 成功响应（泛型：TOutput 为 Skill 输出载荷）。 */
export interface SkillSuccessResponse<TOutput = unknown> {
  status: 'succeeded'
  outputs: TOutput
  assets: SkillAssetRef[]
  quality_flags: QualityFlag[]
  usage: {
    provider?: string
    model?: string
    tokens?: number
    cost?: number | null
  }
  error: null
}

/** Spec §6 Skill 失败响应。usage 可为空对象，error 必填。 */
export interface SkillFailureResponse<TOutput = unknown> {
  status: 'failed'
  outputs: TOutput
  assets: SkillAssetRef[]
  quality_flags: QualityFlag[]
  usage: Record<string, never>
  error: {
    code: import('./errors.js').ErrorCode
    message: string
  }
}

/** Spec §6 Skill Response = 成功 | 失败。 */
export type SkillResponse<TOutput = unknown> =
  | SkillSuccessResponse<TOutput>
  | SkillFailureResponse<TOutput>

/** 构造成功响应的便捷工厂。 */
export function successResponse<TOutput>(
  outputs: TOutput,
  opts: {
    assets?: SkillAssetRef[]
    quality_flags?: QualityFlag[]
    usage?: SkillSuccessResponse<TOutput>['usage']
  } = {},
): SkillSuccessResponse<TOutput> {
  return {
    status: 'succeeded',
    outputs,
    assets: opts.assets ?? [],
    quality_flags: opts.quality_flags ?? [],
    usage: opts.usage ?? {},
    error: null,
  }
}

/** 构造失败响应的便捷工厂。 */
export function failureResponse<TOutput>(
  error: { code: import('./errors.js').ErrorCode; message: string },
  opts: { outputs?: TOutput; assets?: SkillAssetRef[]; quality_flags?: QualityFlag[] } = {},
): SkillFailureResponse<TOutput> {
  return {
    status: 'failed',
    outputs: (opts.outputs ?? {}) as TOutput,
    assets: opts.assets ?? [],
    quality_flags: opts.quality_flags ?? [],
    usage: EMPTY_USAGE as Record<string, never>,
    error,
  }
}

// ────────────────────────────────────────────────────────────────────────────
// 通用结构校验 Schema（input/output 以 unknown 透传，由具体 Skill IO Schema 校验）
// ────────────────────────────────────────────────────────────────────────────

export const SkillRequestEnvelopeSchema = z.object({
  skill_name: z.string().min(1),
  skill_version: z.string().min(1),
  project_id: IdSchema,
  run_id: IdSchema,
  input: z.unknown(),
  config: z.record(z.string(), z.unknown()),
  idempotency_key: z.string().min(1),
})

export const SkillResponseEnvelopeSchema = z.object({
  status: SkillRunStatusSchema,
  outputs: z.unknown(),
  assets: z.array(SkillAssetRefSchema),
  quality_flags: z.array(QualityFlagSchema),
  usage: SkillUsageSchema,
  error: z.union([SkillErrorSchema, z.null()]),
})
