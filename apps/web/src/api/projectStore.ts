import type { KnownProject, KnownRun } from './types'

const PROJECTS_KEY = 'video-multisrt:web:projects'
const RUNS_KEY = 'video-multisrt:web:runs'

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') {
    return fallback
  }
  const raw = window.localStorage.getItem(key)
  if (!raw) {
    return fallback
  }
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function writeJson<T>(key: string, value: T): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(key, JSON.stringify(value))
}

export function getKnownProjects(): KnownProject[] {
  return readJson<KnownProject[]>(PROJECTS_KEY, [])
}

export function rememberProject(project: KnownProject): void {
  const current = getKnownProjects().filter((item) => item.project_id !== project.project_id)
  writeJson(PROJECTS_KEY, [
    {
      ...project,
      updated_at: project.updated_at ?? new Date().toISOString(),
    },
    ...current,
  ].slice(0, 80))
}

export function forgetProject(projectId: string): void {
  writeJson(
    PROJECTS_KEY,
    getKnownProjects().filter((item) => item.project_id !== projectId),
  )
}

export function getKnownRuns(): KnownRun[] {
  return readJson<KnownRun[]>(RUNS_KEY, [])
}

export function rememberRun(projectId: string, runId: string): void {
  const current = getKnownRuns().filter((item) => item.run_id !== runId)
  writeJson(RUNS_KEY, [{ project_id: projectId, run_id: runId, created_at: new Date().toISOString() }, ...current].slice(0, 120))

  const project = getKnownProjects().find((item) => item.project_id === projectId)
  if (project) {
    rememberProject({ ...project, last_run_id: runId, updated_at: new Date().toISOString() })
  }
}

export function getLastRunForProject(projectId: string): string | undefined {
  return getKnownRuns().find((item) => item.project_id === projectId)?.run_id
}
