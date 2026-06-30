/**
 * Spec §8 文件命名规范 —— 对象存储路径生成纯函数。
 *
 * 输出与 Spec §8 文档逐字一致：
 * ```text
 * projects/{project_id}/source/source.mp4
 * projects/{project_id}/source/source.wav
 * projects/{project_id}/separation/vocals.wav
 * projects/{project_id}/separation/background.wav
 * projects/{project_id}/asr/source_segments.json
 * projects/{project_id}/translations/{language}.json
 * projects/{project_id}/subtitles/{language}.srt
 * projects/{project_id}/subtitles/{language}.vtt
 * projects/{project_id}/tts/{language}/{segment_id}.wav
 * projects/{project_id}/audio/{language}.vocal.wav
 * projects/{project_id}/audio/{language}.mix.m4a
 * projects/{project_id}/preview/{language}.mp4
 * projects/{project_id}/packages/{version_id}.zip
 * ```
 *
 * 纯函数：不访问对象存储，仅拼接字符串。
 */
import type { SourceLanguage, TargetLanguage } from './languages.js'
import type { SubtitleFormat } from './enums.js'

const BASE = 'projects'

/** 原视频 / 原始音频：`projects/{id}/source/source.{format}`。 */
export function sourcePath(projectId: string, format: 'mp4' | 'wav' | string): string {
  return `${BASE}/${projectId}/source/source.${format}`
}

/** 声源分离产物：`projects/{id}/separation/{vocals|background}.wav`。 */
export function separationPath(projectId: string, kind: 'vocals' | 'background'): string {
  return `${BASE}/${projectId}/separation/${kind}.wav`
}

/** ASR 原始片段：`projects/{id}/asr/source_segments.json`。 */
export function asrPath(projectId: string): string {
  return `${BASE}/${projectId}/asr/source_segments.json`
}

/** 翻译结果：`projects/{id}/translations/{language}.json`。 */
export function translationsPath(projectId: string, language: TargetLanguage): string {
  return `${BASE}/${projectId}/translations/${language}.json`
}

/** 字幕：`projects/{id}/subtitles/{language}.{srt|vtt}`。 */
export function subtitlePath(
  projectId: string,
  language: TargetLanguage | SourceLanguage,
  format: SubtitleFormat,
): string {
  return `${BASE}/${projectId}/subtitles/${language}.${format}`
}

/** 单句 TTS 音频：`projects/{id}/tts/{language}/{segment_id}.wav`。 */
export function ttsSegmentPath(
  projectId: string,
  language: TargetLanguage,
  segmentId: string,
): string {
  return `${BASE}/${projectId}/tts/${language}/${segmentId}.wav`
}

/** 目标语言音频轨：`projects/{id}/audio/{language}.{vocal.wav|mix.m4a}`。 */
export function audioPath(
  projectId: string,
  language: TargetLanguage,
  kind: 'vocal' | 'mix',
): string {
  return kind === 'vocal'
    ? `${BASE}/${projectId}/audio/${language}.vocal.wav`
    : `${BASE}/${projectId}/audio/${language}.mix.m4a`
}

/** 预览视频：`projects/{id}/preview/{language}.mp4`。 */
export function previewPath(projectId: string, language: TargetLanguage): string {
  return `${BASE}/${projectId}/preview/${language}.mp4`
}

/** 下载包：`projects/{id}/packages/{version_id}.zip`。 */
export function packagePath(projectId: string, versionId: string): string {
  return `${BASE}/${projectId}/packages/${versionId}.zip`
}
