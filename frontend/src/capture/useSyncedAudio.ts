import { useEffect, type RefObject } from 'react'

// Past this much drift the audio is snapped back to the picture.
const MAX_DRIFT_S = 0.15

/**
 * Keeps an <audio> element locked to a <video> element.
 *
 * The character cut-out (isolated.mp4) is silent -- SAM 2 composites frames,
 * not sound -- so the scene's own audio (the trimmed clip) plays alongside it.
 * The video is the clock: play, pause, seek and stalls all follow it.
 */
export function useSyncedAudio(
  videoRef: RefObject<HTMLVideoElement | null>,
  audioRef: RefObject<HTMLAudioElement | null>,
  enabled = true,
) {
  useEffect(() => {
    const video = videoRef.current
    const audio = audioRef.current
    if (!video || !audio) return
    audio.muted = !enabled
    if (!enabled) return

    const snap = () => {
      if (Math.abs(audio.currentTime - video.currentTime) > MAX_DRIFT_S) {
        audio.currentTime = video.currentTime
      }
    }
    const play = () => {
      snap()
      void audio.play().catch(() => {})
    }
    const pause = () => audio.pause()

    video.addEventListener('play', play)
    video.addEventListener('playing', play)
    video.addEventListener('pause', pause)
    video.addEventListener('waiting', pause)
    video.addEventListener('ended', pause)
    video.addEventListener('seeked', snap)
    video.addEventListener('timeupdate', snap)
    if (!video.paused) play()
    return () => {
      video.removeEventListener('play', play)
      video.removeEventListener('playing', play)
      video.removeEventListener('pause', pause)
      video.removeEventListener('waiting', pause)
      video.removeEventListener('ended', pause)
      video.removeEventListener('seeked', snap)
      video.removeEventListener('timeupdate', snap)
      audio.pause()
    }
  }, [videoRef, audioRef, enabled])
}
