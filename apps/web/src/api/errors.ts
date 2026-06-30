import { ERROR_CODE_MESSAGES, type ErrorCode } from '@video-multisrt/shared-types'
import type { ApiErrorBody } from './types'

const EXTRA_ERROR_MESSAGES: Record<string, string> = {
  INVALID_REQUEST: '请求参数不完整或格式不正确',
  UNAUTHORIZED: '登录信息缺失或已失效',
  NOT_FOUND: '资源不存在或已被删除',
}

export class ApiClientError extends Error {
  readonly code: string
  readonly status: number
  readonly details?: unknown

  constructor(error: ApiErrorBody, status: number) {
    super(error.message)
    this.name = 'ApiClientError'
    this.code = error.code
    this.status = status
    this.details = error.details
  }
}

export function isSpecErrorCode(code: string): code is ErrorCode {
  return code in ERROR_CODE_MESSAGES
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    const base = errorCodeToMessage(error.code)
    return error.message && error.message !== base ? `${base}: ${error.message}` : base
  }
  if (typeof error === 'object' && error !== null && 'code' in error) {
    const code = String((error as { code: unknown }).code)
    const message = 'message' in error ? String((error as { message: unknown }).message) : ''
    const base = errorCodeToMessage(code)
    return message && message !== base ? `${base}: ${message}` : base
  }
  if (error instanceof Error) {
    return error.message
  }
  return '请求失败，请稍后重试'
}

export function errorCodeToMessage(code: string | null | undefined): string {
  if (!code) {
    return '未知错误'
  }
  if (isSpecErrorCode(code)) {
    return ERROR_CODE_MESSAGES[code]
  }
  return EXTRA_ERROR_MESSAGES[code] ?? code
}
