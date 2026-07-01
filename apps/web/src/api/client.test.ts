import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from './client'
import { ApiClientError, getErrorMessage } from './errors'

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status || 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('ApiClient', () => {
  it('creates projects with configured base URL and user header', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse({
        project_id: 'proj_1',
        upload_url: 'http://upload.test/source.mp4',
        preview_url: 'http://download.test/source.mp4',
      }),
    )
    const client = new ApiClient({
      baseUrl: 'http://api.test/api/',
      userId: 'user_123',
      fetcher: fetcher as unknown as typeof fetch,
    })

    const response = await client.createProject({
      name: 'episode_01',
      source_language: 'auto',
      target_languages: ['en-US'],
      translation_style: 'short_drama_localized',
    })

    expect(response.project_id).toBe('proj_1')
    expect(response.preview_url).toBe('http://download.test/source.mp4')
    expect(fetcher).toHaveBeenCalledWith(
      'http://api.test/api/projects',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-User-Id': 'user_123',
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          name: 'episode_01',
          source_language: 'auto',
          target_languages: ['en-US'],
          translation_style: 'short_drama_localized',
        }),
      }),
    )
  })

  it('triggers on-demand translate and dubbing runs', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ run_id: 'run_translate', status: 'pending' }))
      .mockResolvedValueOnce(jsonResponse({ run_id: 'run_dub', status: 'pending' }))
    const client = new ApiClient({
      baseUrl: 'http://api.test/api',
      userId: 'user_123',
      fetcher: fetcher as unknown as typeof fetch,
    })

    await expect(client.translateProject('proj_1', { target_language: 'en-US' })).resolves.toEqual({
      run_id: 'run_translate',
      status: 'pending',
    })
    await expect(client.dubProject('proj_1', { target_language: 'es-ES' })).resolves.toEqual({
      run_id: 'run_dub',
      status: 'pending',
    })

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      'http://api.test/api/projects/proj_1/translate',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_language: 'en-US' }),
      }),
    )
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      'http://api.test/api/projects/proj_1/dub',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_language: 'es-ES' }),
      }),
    )
  })

  it('maps API error payloads to user readable messages', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'TRANSLATION_FAILED',
            message: 'Provider request failed',
          },
        },
        { status: 502 },
      ),
    )
    const client = new ApiClient({
      baseUrl: 'http://api.test/api',
      fetcher: fetcher as unknown as typeof fetch,
    })

    await expect(client.getProject('proj_missing')).rejects.toBeInstanceOf(ApiClientError)

    try {
      await client.getProject('proj_missing')
    } catch (error) {
      expect(getErrorMessage(error)).toBe('翻译失败: Provider request failed')
    }
  })
})
