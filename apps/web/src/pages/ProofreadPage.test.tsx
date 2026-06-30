import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProofreadPage } from './ProofreadPage'

function renderRoute() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    [{ path: '/projects/:projectId/proofread', element: <ProofreadPage /> }],
    { initialEntries: ['/projects/proj_1/proofread'] },
  )
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

function response(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

describe('ProofreadPage', () => {
  it('saves edited translation and shows stale downstream hint', async () => {
    const fetcher = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/projects/proj_1')) {
        return response({
          project: {
            project_id: 'proj_1',
            name: 'episode',
            status: 'proofreading',
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

      if (url.includes('/segments') && init?.method !== 'PATCH') {
        return response({
          segments: [
            {
              segment: {
                segment_id: 'seg_1',
                project_id: 'proj_1',
                index: 1,
                start_ms: 1000,
                end_ms: 3000,
                speaker_id: 'spk_1',
                source_language: 'zh-CN',
                source_text: '你想怎样？',
                asr_confidence: 0.92,
                locked: false,
                quality_flags: [],
              },
              translation: {
                translation_id: 'tr_1',
                segment_id: 'seg_1',
                target_language: 'en-US',
                text: 'What do you want?',
                style: 'short_drama_localized',
                model: 'deepseek-default',
                prompt_version: 'short_drama_v1',
                status: 'completed',
                edited_by: null,
                updated_at: '2026-06-30T10:05:00Z',
              },
              tts_job: null,
            },
          ],
        })
      }

      if (url.endsWith('/projects/proj_1/segments/seg_1')) {
        expect(init?.method).toBe('PATCH')
        expect(init?.body).toBe(
          JSON.stringify({
            translations: { 'en-US': 'What exactly do you want?' },
          }),
        )
        return response({
          segment: {
            segment_id: 'seg_1',
            project_id: 'proj_1',
            index: 1,
            start_ms: 1000,
            end_ms: 3000,
            speaker_id: 'spk_1',
            source_language: 'zh-CN',
            source_text: '你想怎样？',
            asr_confidence: 0.92,
            locked: false,
            quality_flags: [],
          },
          translation: {
            translation_id: 'tr_2',
            segment_id: 'seg_1',
            target_language: 'en-US',
            text: 'What exactly do you want?',
            style: 'short_drama_localized',
            model: 'deepseek-default',
            prompt_version: 'short_drama_v1',
            status: 'completed',
            edited_by: 'user_001',
            updated_at: '2026-06-30T10:06:00Z',
          },
          tts_job: null,
        })
      }

      return response({ agent_run: null, skill_runs: [], current_checkpoint: null, quality_flags: [] })
    })
    vi.stubGlobal('fetch', fetcher)

    renderRoute()

    const translation = await screen.findByLabelText('seg_1 translation')
    fireEvent.change(translation, { target: { value: 'What exactly do you want?' } })
    fireEvent.click(screen.getByRole('button', { name: /保存/i }))

    await waitFor(() => {
      expect(screen.getByText('下游产物待重跑')).toBeInTheDocument()
    })
  })
})
