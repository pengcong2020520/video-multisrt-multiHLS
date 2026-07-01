import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { getLastRunForProject } from '../api/projectStore'
import { queryKeys } from '../api/queryKeys'
import type {
  ContinueAgentRunRequest,
  CreatePackageRequest,
  CreateProjectRequest,
  GenerateProjectRequest,
  OnDemandLanguageRequest,
  PatchSegmentRequest,
  ProcessProjectRequest,
} from '../api/types'

export function useKnownProjects() {
  return useQuery({
    queryKey: queryKeys.knownProjects,
    queryFn: () => apiClient.listKnownProjects(),
  })
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project(projectId || ''),
    queryFn: () => apiClient.getProject(projectId || ''),
    enabled: Boolean(projectId),
  })
}

export function useSegments(projectId: string | undefined, targetLanguage: string | undefined) {
  return useQuery({
    queryKey: queryKeys.segments(projectId || '', targetLanguage),
    queryFn: () => apiClient.getSegments(projectId || '', targetLanguage),
    enabled: Boolean(projectId),
  })
}

export function useAgentRun(runId: string | undefined, poll = false) {
  return useQuery({
    queryKey: queryKeys.agentRun(runId),
    queryFn: () => apiClient.getAgentRun(runId || ''),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      if (!poll || !query.state.data) {
        return false
      }
      const status = query.state.data.agent_run.status
      return ['pending', 'planning', 'running'].includes(status) ? 2500 : false
    },
  })
}

export function useProjectLastRun(projectId: string | undefined) {
  const runId = projectId ? getLastRunForProject(projectId) : undefined
  return { runId }
}

export function useManifest(projectId: string | undefined, versionId?: string) {
  return useQuery({
    queryKey: queryKeys.manifest(projectId || '', versionId),
    queryFn: () => apiClient.getManifest(projectId || '', versionId),
    enabled: Boolean(projectId),
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateProjectRequest) => apiClient.createProject(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.knownProjects })
    },
  })
}

export function useProcessProject(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ProcessProjectRequest) => apiClient.processProject(projectId || '', payload),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId || '') })
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentRun(run.run_id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.knownProjects })
    },
  })
}

export function useTranslateProject(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: OnDemandLanguageRequest) =>
      apiClient.translateProject(projectId || '', payload),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId || '') })
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentRun(run.run_id) })
      void queryClient.invalidateQueries({ queryKey: ['manifest', projectId || ''] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.knownProjects })
    },
  })
}

export function useDubProject(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: OnDemandLanguageRequest) => apiClient.dubProject(projectId || '', payload),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId || '') })
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentRun(run.run_id) })
      void queryClient.invalidateQueries({ queryKey: ['manifest', projectId || ''] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.knownProjects })
    },
  })
}

export function usePatchSegment(projectId: string | undefined, targetLanguage: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ segmentId, payload }: { segmentId: string; payload: PatchSegmentRequest }) =>
      apiClient.patchSegment(projectId || '', segmentId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.segments(projectId || '', targetLanguage),
      })
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId || '') })
    },
  })
}

export function useContinueRun(runId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ContinueAgentRunRequest) => apiClient.continueAgentRun(runId || '', payload),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentRun(run.run_id) })
    },
  })
}

export function useGenerateProject(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: GenerateProjectRequest) => apiClient.generateProject(projectId || '', payload),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId || '') })
      void queryClient.invalidateQueries({ queryKey: queryKeys.agentRun(run.run_id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.knownProjects })
    },
  })
}

export function useCreatePackage(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreatePackageRequest) => apiClient.createPackage(projectId || '', payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId || '') })
    },
  })
}
