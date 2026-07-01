import { Download, Subtitles, Volume2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ManifestResponse } from '../api/types'
import { activeCueAt, parseWebVtt, type VttCue } from '../lib/vtt'

interface CustomPlayerProps {
  manifest: ManifestResponse
  subtitleLanguage?: string
  audioLanguage?: string
  onSubtitleLanguageChange?: (language: string) => void
  onAudioLanguageChange?: (language: string) => void
}

export function CustomPlayer({
  manifest,
  subtitleLanguage: controlledSubtitleLanguage,
  audioLanguage: controlledAudioLanguage,
  onSubtitleLanguageChange,
  onAudioLanguageChange,
}: CustomPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [internalSubtitleLanguage, setInternalSubtitleLanguage] = useState<string>('none')
  const [internalAudioLanguage, setInternalAudioLanguage] = useState<string>('video')
  const [cues, setCues] = useState<VttCue[]>([])
  const [currentTime, setCurrentTime] = useState(0)
  const [subtitleError, setSubtitleError] = useState<string | null>(null)
  const subtitleLanguage = controlledSubtitleLanguage ?? internalSubtitleLanguage
  const audioLanguage = controlledAudioLanguage ?? internalAudioLanguage

  const selectedSubtitle = useMemo(
    () => manifest.subtitles.find((item) => item.language === subtitleLanguage),
    [manifest.subtitles, subtitleLanguage],
  )

  const selectedAudio = useMemo(
    () => manifest.audio_tracks.find((item) => item.language === audioLanguage),
    [manifest.audio_tracks, audioLanguage],
  )

  const activeCue = subtitleLanguage === 'none' ? undefined : activeCueAt(cues, currentTime)

  useEffect(() => {
    if (
      subtitleLanguage !== 'none' &&
      !manifest.subtitles.some((subtitle) => subtitle.language === subtitleLanguage)
    ) {
      changeSubtitleLanguage('none')
    }
    if (
      audioLanguage !== 'video' &&
      !manifest.audio_tracks.some((track) => track.language === audioLanguage)
    ) {
      changeAudioLanguage('video')
    }
  }, [
    manifest.project_id,
    manifest.version_id,
    manifest.subtitles,
    manifest.audio_tracks,
    subtitleLanguage,
    audioLanguage,
  ])

  useEffect(() => {
    let cancelled = false
    setCues([])
    setSubtitleError(null)

    if (!selectedSubtitle) {
      return
    }

    fetch(selectedSubtitle.url)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.text()
      })
      .then((text) => {
        if (!cancelled) {
          setCues(parseWebVtt(text))
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setSubtitleError(error instanceof Error ? error.message : '字幕加载失败')
        }
      })

    return () => {
      cancelled = true
    }
  }, [selectedSubtitle])

  useEffect(() => {
    const video = videoRef.current
    const audio = audioRef.current
    if (!video || !audio) {
      return
    }

    if (selectedAudio) {
      video.muted = true
      if (audio.getAttribute('src') !== selectedAudio.url) {
        audio.src = selectedAudio.url
      }
      syncAudioToVideo()
      if (!video.paused) {
        void audio.play()
      }
    } else {
      video.muted = false
      audio.pause()
      audio.removeAttribute('src')
    }
  }, [selectedAudio])

  function changeSubtitleLanguage(language: string) {
    setInternalSubtitleLanguage(language)
    onSubtitleLanguageChange?.(language)
  }

  function changeAudioLanguage(language: string) {
    setInternalAudioLanguage(language)
    onAudioLanguageChange?.(language)
  }

  function syncAudioToVideo(force = false) {
    const video = videoRef.current
    const audio = audioRef.current
    if (!video || !audio || !selectedAudio) {
      return
    }
    const drift = Math.abs(audio.currentTime - video.currentTime)
    if (force || drift > 0.25) {
      try {
        audio.currentTime = video.currentTime
      } catch {
        // Some browsers reject currentTime updates before metadata is ready.
      }
    }
    audio.volume = video.volume
  }

  function handlePlay() {
    syncAudioToVideo(true)
    if (selectedAudio) {
      void audioRef.current?.play()
    }
  }

  function handlePause() {
    audioRef.current?.pause()
  }

  function handleTimeUpdate() {
    const video = videoRef.current
    if (!video) {
      return
    }
    setCurrentTime(video.currentTime)
    syncAudioToVideo()
  }

  function handleSeeking() {
    syncAudioToVideo(true)
  }

  function handleVolumeChange() {
    const video = videoRef.current
    const audio = audioRef.current
    if (video && audio) {
      audio.volume = video.volume
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-lg bg-black">
        <video
          ref={videoRef}
          className="aspect-video w-full bg-black"
          src={manifest.video.url}
          controls
          playsInline
          preload="metadata"
          onPlay={handlePlay}
          onPause={handlePause}
          onTimeUpdate={handleTimeUpdate}
          onSeeking={handleSeeking}
          onSeeked={handleSeeking}
          onVolumeChange={handleVolumeChange}
          data-testid="preview-video"
        />
        <audio ref={audioRef} preload="metadata" data-testid="preview-audio" />
        {activeCue ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-14 flex justify-center px-4">
            <div className="max-w-3xl rounded-md bg-black/78 px-4 py-2 text-center text-lg font-semibold leading-snug text-white shadow-soft">
              {activeCue.text}
            </div>
          </div>
        ) : null}
      </div>

      <div className="grid gap-3 rounded-lg border border-line bg-white p-3 md:grid-cols-[1fr_1fr_auto]">
        <label className="text-sm font-medium text-slate-700">
          <span className="mb-1 flex items-center gap-2">
            <Subtitles className="h-4 w-4" aria-hidden="true" />
            字幕
          </span>
          <select
            className="field"
            value={subtitleLanguage}
            onChange={(event) => changeSubtitleLanguage(event.target.value)}
            data-testid="subtitle-select"
          >
            <option value="none">无字幕</option>
            {manifest.subtitles.map((subtitle) => (
              <option key={`${subtitle.language}-${subtitle.url}`} value={subtitle.language}>
                {subtitle.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium text-slate-700">
          <span className="mb-1 flex items-center gap-2">
            <Volume2 className="h-4 w-4" aria-hidden="true" />
            音轨
          </span>
          <select
            className="field"
            value={audioLanguage}
            onChange={(event) => changeAudioLanguage(event.target.value)}
            data-testid="audio-select"
          >
            <option value="video">视频内置音轨</option>
            {manifest.audio_tracks.map((track) => (
              <option key={`${track.language}-${track.url}`} value={track.language}>
                {track.label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end">
          <a className="btn" href={manifest.video.url} download>
            <Download className="h-4 w-4" aria-hidden="true" />
            视频
          </a>
        </div>
      </div>

      <div className="min-h-7 text-sm text-slate-700" data-testid="active-caption">
        {subtitleError ? <span className="text-red-700">{subtitleError}</span> : activeCue?.text || ''}
      </div>
    </div>
  )
}
