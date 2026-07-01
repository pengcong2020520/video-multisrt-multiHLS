import type {
  AgentRunStatus,
  AgentTemplate,
  AssetType,
  GenerateScope,
  GenerationStep,
  ProcessingStatus,
  ProjectStatus,
  SkillRunStatus,
  SourceLanguage,
  TargetLanguage,
  TaskStatus,
} from '@video-multisrt/shared-types'

export type {
  AgentRunStatus,
  AgentTemplate,
  AssetType,
  GenerateScope,
  GenerationStep,
  ProcessingStatus,
  ProjectStatus,
  SkillRunStatus,
  SourceLanguage,
  TargetLanguage,
  TaskStatus,
}

export type TranslationStyle =
  | 'short_drama_localized'
  | 'high_emotion'
  | 'platform_natural'

export interface CreateProjectRequest {
  name: string
  source_language: SourceLanguage
  target_languages?: TargetLanguage[]
  translation_style?: TranslationStyle | string
}

export interface CreateProjectResponse {
  project_id: string
  upload_url: string
  preview_url: string
}

export interface ProcessProjectRequest {
  enable_source_separation: boolean
  enable_diarization: boolean
  generate_tts: boolean
  generate_preview_mp4: boolean
  agent_template: AgentTemplate
}

export interface RunResponse {
  run_id: string
  status: AgentRunStatus
}

export interface OnDemandLanguageRequest {
  target_language: TargetLanguage | string
}

export interface ContinueAgentRunRequest {
  checkpoint: string
  confirmed: boolean
}

export interface ProjectEntity {
  project_id: string
  name: string
  status: ProjectStatus | string
  source_language: SourceLanguage | string
  target_languages: string[]
  duration_ms: number | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface MediaAssetEntity {
  asset_id: string
  project_id: string
  type: AssetType | string
  language: string | null
  uri: string
  format: string | null
  duration_ms: number | null
  size_bytes: number | null
  checksum: string | null
  created_at: string
}

export interface TaskEntity {
  task_id: string
  project_id: string
  run_id: string | null
  type: string
  status: TaskStatus | string
  target_language: string | null
  error_code: string | null
  error_message: string | null
  retry_count: number
  created_at: string
  updated_at: string
}

export interface QueryProjectResponse {
  project: ProjectEntity
  tasks: TaskEntity[]
  assets: MediaAssetEntity[]
  languages: string[]
}

export interface SegmentEntity {
  segment_id: string
  project_id: string
  index: number
  start_ms: number
  end_ms: number
  speaker_id: string | null
  source_language: string
  source_text: string
  asr_confidence: number | null
  locked: boolean
  quality_flags: string[]
}

export interface TranslationEntity {
  translation_id: string
  segment_id: string
  target_language: string
  text: string
  style: string
  model: string | null
  prompt_version: string | null
  status: ProcessingStatus | string
  edited_by: string | null
  updated_at: string
}

export interface TTSJobEntity {
  tts_job_id: string
  project_id: string
  segment_id: string
  target_language: string
  text: string
  voice_id: string | null
  target_duration_ms: number | null
  speed: number
  status: ProcessingStatus | string
  output_asset_id: string | null
  actual_duration_ms: number | null
  provider: string | null
  provider_task_id: string | null
  error: ApiErrorBody | null
}

export interface SegmentBundle {
  segment: SegmentEntity
  translation: TranslationEntity | null
  tts_job: TTSJobEntity | null
}

export interface QuerySegmentsResponse {
  segments: SegmentBundle[]
}

export interface PatchSegmentRequest {
  start_ms?: number
  end_ms?: number
  speaker_id?: string | null
  source_text?: string
  translations?: Record<string, string>
  locked?: boolean
}

export interface GenerateProjectRequest {
  target_language: string
  scope: GenerateScope
  steps: GenerationStep[]
  segment_ids: string[]
  agent_template: AgentTemplate
}

export interface AgentRunEntity {
  run_id: string
  project_id: string
  version_id: string | null
  template: string
  status: AgentRunStatus | string
  current_step: string | null
  source_language: string
  target_languages: string[]
  created_by: string
  created_at: string
  updated_at: string
}

export interface SkillRunEntity {
  skill_run_id: string
  run_id: string
  project_id: string
  skill_name: string
  skill_version: string
  status: SkillRunStatus | string
  target_language: string | null
  started_at: string | null
  finished_at: string | null
  input_refs: string[]
  output_refs: string[]
  provider: string | null
  model: string | null
  error: ApiErrorBody | null
}

export interface QueryAgentRunResponse {
  agent_run: AgentRunEntity
  skill_runs: SkillRunEntity[]
  current_checkpoint: string | null
  quality_flags: string[]
}

export interface ManifestVideo {
  url: string
  duration_ms: number | null
}

export interface ManifestSubtitle {
  language: string
  label: string
  format: 'vtt' | 'srt' | string
  url: string
}

export interface ManifestAudioTrack {
  language: string
  label: string
  url: string
}

export interface ManifestDownload {
  type: string
  label: string
  url: string
}

export interface ManifestResponse {
  project_id: string
  version_id: string
  video: ManifestVideo
  subtitles: ManifestSubtitle[]
  audio_tracks: ManifestAudioTrack[]
  downloads: ManifestDownload[]
}

export interface CreatePackageRequest {
  version_id: string
  languages: string[]
  include_intermediate_assets: boolean
}

export interface CreatePackageResponse {
  package_id: string
  status: TaskStatus | string
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: unknown
}

export interface ErrorPayload {
  error: ApiErrorBody
}

export interface KnownProject {
  project_id: string
  name: string
  created_at: string
  last_run_id?: string
  updated_at?: string
}

export interface KnownRun {
  run_id: string
  project_id: string
  created_at: string
}
