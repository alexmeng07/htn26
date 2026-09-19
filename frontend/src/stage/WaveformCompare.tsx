import { useEffect, useRef, type RefObject } from 'react'

export interface Waveforms {
  hop_s: number
  original: { db: number[]; voiced: boolean[] }
  player: { db: number[]; voiced: boolean[] }
}

// dBFS -> bar height. Quieter than FLOOR draws as silence.
const FLOOR_DB = -60

/**
 * The original clip's audio above the player's microphone, on one timeline.
 *
 * Bars are loudness per 50 ms. Coral bands mark beats where exactly one of the
 * two was speaking -- a line the player missed, or noise where the character
 * held a pause. A playhead follows the replay; clicking seeks it.
 */
export default function WaveformCompare({
  data,
  videoRef,
  originalLabel,
  originalColour,
  playerColour,
  gapColour,
}: {
  data: Waveforms
  videoRef: RefObject<HTMLVideoElement | null>
  originalLabel: string
  originalColour: string
  playerColour: string
  gapColour: string
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let handle = 0
    const n = Math.min(data.original.db.length, data.player.db.length)
    const duration = n * data.hop_s

    const draw = () => {
      handle = requestAnimationFrame(draw)
      const canvas = canvasRef.current
      if (!canvas || !n) return
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(h * dpr)
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      const lane = h / 2
      const step = w / n
      const level = (db: number) => Math.max(0, Math.min(1, (db - FLOOR_DB) / -FLOOR_DB))

      // Mismatch bands first, behind the bars.
      ctx.fillStyle = gapColour
      ctx.globalAlpha = 0.28
      for (let i = 0; i < n; i++) {
        if (data.original.voiced[i] !== data.player.voiced[i]) ctx.fillRect(i * step, 0, step + 0.5, h)
      }
      ctx.globalAlpha = 1

      const bars = (db: number[], mid: number, colour: string) => {
        ctx.fillStyle = colour
        const bw = Math.max(1, step * 0.7)
        for (let i = 0; i < n; i++) {
          const half = level(db[i]) * (lane / 2 - 4)
          ctx.fillRect(i * step + (step - bw) / 2, mid - half, bw, Math.max(1, half * 2))
        }
      }
      bars(data.original.db, lane / 2, originalColour)
      bars(data.player.db, lane + lane / 2, playerColour)

      // Lane divider.
      ctx.fillStyle = 'rgba(255,255,255,0.15)'
      ctx.fillRect(0, lane, w, 1)

      // Playhead.
      const video = videoRef.current
      if (video && duration) {
        const x = Math.min(1, video.currentTime / duration) * w
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(x - 1, 0, 2, h)
      }
    }
    handle = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(handle)
  }, [data, videoRef, originalColour, playerColour, gapColour])

  const seek = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const video = videoRef.current
    const n = Math.min(data.original.db.length, data.player.db.length)
    if (!video || !n) return
    const rect = e.currentTarget.getBoundingClientRect()
    video.currentTime = ((e.clientX - rect.left) / rect.width) * n * data.hop_s
  }

  return (
    <div className="w-full">
      <div className="relative">
        <canvas ref={canvasRef} onClick={seek} className="block h-32 w-full cursor-pointer" />
        <span className="cv-label pointer-events-none absolute left-2 top-1.5" style={{ color: originalColour }}>
          {originalLabel}
        </span>
        <span className="cv-label pointer-events-none absolute left-2 top-[calc(50%+6px)]" style={{ color: playerColour }}>
          You · microphone
        </span>
      </div>
      <p className="mt-2 flex items-center gap-2 text-xs text-white/60">
        <span className="inline-block h-3 w-3" style={{ background: gapColour, opacity: 0.6 }} />
        One of you was speaking while the other was silent. Click the waveform to jump there.
      </p>
    </div>
  )
}
