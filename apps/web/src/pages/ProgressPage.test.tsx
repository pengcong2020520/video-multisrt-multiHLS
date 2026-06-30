import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProgressPage } from './ProgressPage'

function response(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

describe('ProgressPage', () => {
  it('shows run status and mapped skill errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/projects/proj_1')) {
          return response({
            project: {
              project_id: 'proj_1',
              name: 'episode',
              status: 'processing',
              source_language: 'zh-CN',
              target_languages: ['en-US'],
              duration_ms: 120000,
              created_by: 'user_001',
              created_at: '2026-06-30T10:00:00Z',
              updated_at: '2026-06-30T10:05:00Z',
            },
            tasks: [],
            assets: [],
            languages: ['en-US'],
          })
        }
        return response({
          agent_run: {
            run_id: 'run_1',
            project_id: 'proj_1',
            version_id: 'ver_1',
            template: 'full_dubbing',
            status: 'failed',
            current_step: 'voice.synthesize',
            source_language: 'zh-CN',
            target_languages: ['en-US'],
            created_by: 'user_001',
            created_at: '2026-06-30T10:00:00Z',
            updated_at: '2026-06-30T10:05:00Z',
          },
          skill_runs: [
            {
              skill_run_id: 'skill_1',
              run_id: 'run_1',
              project_id: 'proj_1',
              skill_name: 'voice.synthesize',
              skill_version: '1.0.0',
              status: 'failed',
              target_language: 'en-US',
              started_at: '2026-06-30T10:04:00Z',
              finished_at: '2026-06-30T10:05:00Z',
              input_refs: [],
              output_refs: [],
              provider: 'minimax',
              model: null,
              error: { code: 'TTS_FAILED', message: 'Provider request failed' },
            },
          ],
          current_checkpoint: null,
          quality_flags: ['duration_drift'],
        })
      }),
    )

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const router = createMemoryRouter(
      [{ path: '/projects/:projectId/progress', element: <ProgressPage /> }],
      { initialEntries: ['/projects/proj_1/progress?run_id=run_1'] },
    )

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('voice.synthesize')).toBeInTheDocument()
    expect(screen.getByText(/TTS 失败/)).toBeInTheDocument()
    expect(screen.getByText('duration_drift')).toBeInTheDocument()
  })
})
