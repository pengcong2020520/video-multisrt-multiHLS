import { ApiClientError } from './errors'
import {
  getKnownProjects,
  rememberProject,
  rememberRun,
} from './projectStore'
import type {
  ContinueAgentRunRequest,
  CreatePackageRequest,
  CreatePackageResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  ErrorPayload,
  GenerateProjectRequest,
  KnownProject,
  ManifestResponse,
  OnDemandLanguageRequest,
  PatchSegmentRequest,
  ProcessProjectRequest,
  QueryAgentRunResponse,
  QueryProjectResponse,
  QuerySegmentsResponse,
  RunResponse,
  SegmentBundle,
} from './types'

export interface ApiClientOptions {
  baseUrl?: string
  userId?: string
  fetcher?: typeof fetch
}

const DEFAULT_API_BASE_URL = 'http://localhost:8000/api'

function resolveBaseUrl(baseUrl?: string): string {
  const raw = baseUrl || import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
  return raw.replace(/\/+$/, '')
}

function resolveUserId(userId?: string): string {
  return userId || import.meta.env.VITE_USER_ID || 'dev_user'
}

export class ApiClient {
  private readonly baseUrl: string
  private readonly userId: string
  private readonly fetcher: typeof fetch

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = resolveBaseUrl(options.baseUrl)
    this.userId = resolveUserId(options.userId)
    this.fetcher = options.fetcher ?? fetch
  }

  createProject(payload: CreateProjectRequest): Promise<CreateProjectResponse> {
    return this.request<CreateProjectResponse>('/projects', {
      method: 'POST',
      body: payload,
    }).then((response) => {
      rememberProject({
        project_id: response.project_id,
        name: payload.name,
        created_at: new Date().toISOString(),
      })
      return response
    })
  }

  async uploadSourceVideo(uploadUrl: string, file: File): Promise<void> {
    const response = await this.fetcher(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
      },
      body: file,
    })
    if (!response.ok) {
      throw new ApiClientError(
        {
          code: 'INVALID_VIDEO',
          message: `Upload failed with HTTP ${response.status}`,
        },
        response.status,
      )
    }
  }

  processProject(projectId: string, payload: ProcessProjectRequest): Promise<RunResponse> {
    return this.request<RunResponse>(`/projects/${encodeURIComponent(projectId)}/process`, {
      method: 'POST',
      body: payload,
    }).then((response) => {
      rememberRun(projectId, response.run_id)
      return response
    })
  }

  translateProject(projectId: string, payload: OnDemandLanguageRequest): Promise<RunResponse> {
    return this.request<RunResponse>(`/projects/${encodeURIComponent(projectId)}/translate`, {
      method: 'POST',
      body: payload,
    }).then((response) => {
      rememberRun(projectId, response.run_id)
      return response
    })
  }

  dubProject(projectId: string, payload: OnDemandLanguageRequest): Promise<RunResponse> {
    return this.request<RunResponse>(`/projects/${encodeURIComponent(projectId)}/dub`, {
      method: 'POST',
      body: payload,
    }).then((response) => {
      rememberRun(projectId, response.run_id)
      return response
    })
  }

  getAgentRun(runId: string): Promise<QueryAgentRunResponse> {
    return this.request<QueryAgentRunResponse>(`/agent-runs/${encodeURIComponent(runId)}`)
  }

  continueAgentRun(runId: string, payload: ContinueAgentRunRequest): Promise<RunResponse> {
    return this.request<RunResponse>(`/agent-runs/${encodeURIComponent(runId)}/continue`, {
      method: 'POST',
      body: payload,
    })
  }

  getProject(projectId: string): Promise<QueryProjectResponse> {
    return this.request<QueryProjectResponse>(`/projects/${encodeURIComponent(projectId)}`).then(
      (response) => {
        rememberProject({
          project_id: response.project.project_id,
          name: response.project.name,
          created_at: response.project.created_at,
          updated_at: response.project.updated_at,
        })
        return response
      },
    )
  }

  getSegments(projectId: string, targetLanguage?: string): Promise<QuerySegmentsResponse> {
    const query = targetLanguage ? `?target_language=${encodeURIComponent(targetLanguage)}` : ''
    return this.request<QuerySegmentsResponse>(
      `/projects/${encodeURIComponent(projectId)}/segments${query}`,
    )
  }

  patchSegment(
    projectId: string,
    segmentId: string,
    payload: PatchSegmentRequest,
  ): Promise<SegmentBundle> {
    return this.request<SegmentBundle>(
      `/projects/${encodeURIComponent(projectId)}/segments/${encodeURIComponent(segmentId)}`,
      {
        method: 'PATCH',
        body: payload,
      },
    )
  }

  generateProject(projectId: string, payload: GenerateProjectRequest): Promise<RunResponse> {
    return this.request<RunResponse>(`/projects/${encodeURIComponent(projectId)}/generate`, {
      method: 'POST',
      body: payload,
    }).then((response) => {
      rememberRun(projectId, response.run_id)
      return response
    })
  }

  getManifest(projectId: string, versionId?: string): Promise<ManifestResponse> {
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : ''
    return this.request<ManifestResponse>(
      `/projects/${encodeURIComponent(projectId)}/manifest${query}`,
    )
  }

  createPackage(projectId: string, payload: CreatePackageRequest): Promise<CreatePackageResponse> {
    return this.request<CreatePackageResponse>(`/projects/${encodeURIComponent(projectId)}/packages`, {
      method: 'POST',
      body: payload,
    })
  }

  async listKnownProjects(): Promise<QueryProjectResponse[]> {
    const known = getKnownProjects()
    const results = await Promise.allSettled(known.map((item) => this.getProject(item.project_id)))
    return results
      .filter((result): result is PromiseFulfilledResult<QueryProjectResponse> => result.status === 'fulfilled')
      .map((result) => result.value)
  }

  getKnownProjectSummaries(): KnownProject[] {
    return getKnownProjects()
  }

  private async request<T>(
    path: string,
    options: {
      method?: string
      body?: unknown
    } = {},
  ): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method: options.method ?? 'GET',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-User-Id': this.userId,
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })

    if (!response.ok) {
      throw await this.toClientError(response)
    }

    if (response.status === 204) {
      return undefined as T
    }

    return (await response.json()) as T
  }

  private async toClientError(response: Response): Promise<ApiClientError> {
    try {
      const payload = (await response.json()) as ErrorPayload
      if (payload?.error?.code && payload.error.message) {
        return new ApiClientError(payload.error, response.status)
      }
    } catch {
      // Fall through to the generic HTTP error below.
    }
    return new ApiClientError(
      {
        code: 'HTTP_ERROR',
        message: `HTTP ${response.status}`,
      },
      response.status,
    )
  }
}

export const apiClient = new ApiClient()
