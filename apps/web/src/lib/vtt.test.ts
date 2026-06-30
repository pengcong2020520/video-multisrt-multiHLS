import { describe, expect, it } from 'vitest'
import { activeCueAt, parseVttTimestamp, parseWebVtt } from './vtt'

describe('WebVTT parser', () => {
  it('parses timestamps and active cues', () => {
    const cues = parseWebVtt(`WEBVTT

1
00:00:01.000 --> 00:00:03.500
Hello

2
00:00:04.000 --> 00:00:05.000
World`)

    expect(parseVttTimestamp('01:02:03.500')).toBe(3723.5)
    expect(cues).toHaveLength(2)
    expect(activeCueAt(cues, 2)?.text).toBe('Hello')
    expect(activeCueAt(cues, 3.8)).toBeUndefined()
  })
})
