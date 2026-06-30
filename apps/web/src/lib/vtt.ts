export interface VttCue {
  id?: string
  start: number
  end: number
  text: string
}

const TIMING_SEPARATOR = /\s+-->\s+/

export function parseVttTimestamp(value: string): number {
  const clean = value.trim().replace(',', '.')
  const parts = clean.split(':')
  if (parts.length < 2 || parts.length > 3) {
    return 0
  }
  const seconds = Number(parts.pop())
  const minutes = Number(parts.pop())
  const hours = parts.length ? Number(parts.pop()) : 0
  if ([hours, minutes, seconds].some((part) => Number.isNaN(part))) {
    return 0
  }
  return hours * 3600 + minutes * 60 + seconds
}

export function parseWebVtt(input: string): VttCue[] {
  const normalized = input.replace(/\r/g, '').trim()
  if (!normalized) {
    return []
  }

  return normalized
    .split(/\n{2,}/)
    .flatMap((block) => {
      const lines = block
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)

      if (!lines.length || lines[0] === 'WEBVTT' || lines[0].startsWith('NOTE')) {
        return []
      }

      const timingIndex = lines.findIndex((line) => TIMING_SEPARATOR.test(line))
      if (timingIndex === -1) {
        return []
      }

      const [startRaw, endRaw] = lines[timingIndex].split(TIMING_SEPARATOR)
      const endValue = endRaw.split(/\s+/)[0]
      const text = lines.slice(timingIndex + 1).join('\n')
      if (!text) {
        return []
      }

      return [
        {
          id: timingIndex > 0 ? lines[0] : undefined,
          start: parseVttTimestamp(startRaw),
          end: parseVttTimestamp(endValue),
          text,
        },
      ]
    })
    .sort((a, b) => a.start - b.start)
}

export function activeCueAt(cues: VttCue[], time: number): VttCue | undefined {
  return cues.find((cue) => time >= cue.start && time < cue.end)
}
