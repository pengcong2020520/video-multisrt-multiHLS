import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CustomPlayer } from './CustomPlayer'
import type { ManifestResponse } from '../api/types'

const manifest: ManifestResponse = {
  project_id: 'proj_1',
  version_id: 'ver_1',
  video: {
    url: 'http://cdn.test/source.mp4',
    duration_ms: 5000,
  },
  subtitles: [
    {
      language: 'en-US',
      label: 'English',
      format: 'vtt',
      url: 'http://cdn.test/en.vtt',
    },
  ],
  audio_tracks: [
    {
      language: 'source',
      label: '原音轨',
      url: 'http://cdn.test/source.m4a',
    },
    {
      language: 'en-US',
      label: 'English Dub',
      url: 'http://cdn.test/en.m4a',
    },
  ],
  downloads: [],
}

describe('CustomPlayer', () => {
  it('renders custom subtitles and syncs external audio to video time', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(`WEBVTT

00:00:01.000 --> 00:00:03.000
What do you want?`),
      ),
    )

    render(<CustomPlayer manifest={manifest} />)

    fireEvent.change(screen.getByTestId('subtitle-select'), {
      target: { value: 'en-US' },
    })
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('http://cdn.test/en.vtt'))

    const video = screen.getByTestId('preview-video') as HTMLVideoElement
    const audio = screen.getByTestId('preview-audio') as HTMLAudioElement

    expect(screen.getByTestId('audio-select')).toHaveValue('video')

    video.currentTime = 2
    audio.currentTime = 0
    fireEvent.timeUpdate(video)

    expect(screen.getByTestId('active-caption')).toHaveTextContent('What do you want?')
    expect(audio.currentTime).toBe(0)

    fireEvent.change(screen.getByTestId('audio-select'), {
      target: { value: 'en-US' },
    })
    fireEvent.timeUpdate(video)
    expect(audio.src).toContain('/en.m4a')
    expect(audio.currentTime).toBe(2)
    expect(video.muted).toBe(true)
  })
})
