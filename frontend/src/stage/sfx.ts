import { mediaUrl } from '../api/client'

/** Cached ElevenLabs sound effects, generated once by `python -m server.voice.setup`. */
export type Sfx = 'drumroll' | 'yes_ding' | 'no_buzzer' | 'applause' | 'golden_buzzer' | 'confetti_pop'

/**
 * Fire-and-forget. A missing file or a blocked autoplay must never stall the
 * show, so every failure is swallowed.
 */
export function playSfx(name: Sfx, { loop = false, volume = 1 } = {}): HTMLAudioElement {
  const audio = new Audio(mediaUrl(`/sfx/${name}.mp3`))
  audio.loop = loop
  audio.volume = volume
  audio.play().catch(() => {})
  return audio
}
