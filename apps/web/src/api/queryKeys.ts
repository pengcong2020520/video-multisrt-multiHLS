export const queryKeys = {
  knownProjects: ['known-projects'] as const,
  project: (projectId: string) => ['project', projectId] as const,
  agentRun: (runId: string | undefined) => ['agent-run', runId] as const,
  segments: (projectId: string, language: string | undefined) =>
    ['segments', projectId, language] as const,
  manifest: (projectId: string, versionId: string | undefined) =>
    ['manifest', projectId, versionId] as const,
}
