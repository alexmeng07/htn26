import { useEffect, useRef, type RefObject } from 'react'
import { FaceLandmarker, PoseLandmarker } from '@mediapipe/tasks-vision'

/** One frame of drawable points, normalised to the video frame (0..1). */
export interface OverlayFrame {
  pose: number[][] // [x, y, visibility] x 33, or empty
  face: number[][] // [x, y] x 478 face-mesh landmarks, or empty
}

// Only what the camera can actually see gets drawn -- the "smart" part. A
// close-up shows head, shoulders and any hand that comes into shot; a wide shot
// shows the whole body, with no per-scene configuration.
const VISIBLE = 0.5
// Pose points 0-10 are the face; the face mesh draws it better when present.
const POSE_FACE = 10
// The pose model estimates joints just past the frame edge and still calls
// them visible (shoulders under a close-up). Only draw what is IN the picture.
const EDGE = 0.01
const inFrame = (p: number[]) => p[0] >= -EDGE && p[0] <= 1 + EDGE && p[1] >= -EDGE && p[1] <= 1 + EDGE

/**
 * Draws a skeleton (and face contour) over a <video>, in step with it.
 *
 * The canvas sits on top of the video element and works out where the picture
 * actually lands inside it (object-fit contain or cover), so points line up
 * whatever the box size. Mirror it with the same CSS as the video. Drawing only:
 * nothing here is scored (R5.9).
 */
export default function SkeletonOverlay({
  videoRef,
  frame,
  fit,
  colour,
  className = '',
}: {
  videoRef: RefObject<HTMLVideoElement | null>
  /** Called every animation frame; returns what to draw now (or null). */
  frame: () => OverlayFrame | null
  fit: 'contain' | 'cover'
  colour: string
  className?: string
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let handle = 0
    const draw = () => {
      handle = requestAnimationFrame(draw)
      const canvas = canvasRef.current
      const video = videoRef.current
      if (!canvas || !video) return
      const dpr = window.devicePixelRatio || 1
      const bw = video.clientWidth
      const bh = video.clientHeight
      if (canvas.width !== Math.round(bw * dpr) || canvas.height !== Math.round(bh * dpr)) {
        canvas.width = Math.round(bw * dpr)
        canvas.height = Math.round(bh * dpr)
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, bw, bh)

      const data = frame()
      const vw = video.videoWidth
      const vh = video.videoHeight
      if (!data || !vw || !vh) return

      // Where the picture sits inside the element.
      const scale = fit === 'contain' ? Math.min(bw / vw, bh / vh) : Math.max(bw / vw, bh / vh)
      const pw = vw * scale
      const ph = vh * scale
      const ox = (bw - pw) / 2
      const oy = (bh - ph) / 2
      const at = (p: number[]): [number, number] => [ox + p[0] * pw, oy + p[1] * ph]

      ctx.strokeStyle = colour
      ctx.fillStyle = colour
      ctx.lineCap = 'round'

      const hasFace = data.face.length > 0
      const detected = (i: number) =>
        (data.pose[i]?.[2] ?? 0) >= VISIBLE && !(hasFace && i <= POSE_FACE)
      // A joint gets a dot only when it's in the picture; a bone is drawn when
      // either end is, and the clip cuts it at the edge -- so a hand coming into
      // shot shows its forearm entering from below, as it looks on screen.
      const seen = (i: number) => detected(i) && inFrame(data.pose[i])
      const bone = (a: number, b: number) => detected(a) && detected(b) && (seen(a) || seen(b))

      // Never paint outside the picture (object-fit contain leaves black bars).
      ctx.save()
      ctx.beginPath()
      ctx.rect(ox, oy, pw, ph)
      ctx.clip()

      ctx.lineWidth = 3
      ctx.globalAlpha = 0.9
      ctx.beginPath()
      for (const { start, end } of PoseLandmarker.POSE_CONNECTIONS) {
        if (!bone(start, end)) continue
        const [x1, y1] = at(data.pose[start])
        const [x2, y2] = at(data.pose[end])
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
      }
      ctx.stroke()
      for (let i = 0; i < data.pose.length; i++) {
        if (!seen(i)) continue
        const [x, y] = at(data.pose[i])
        ctx.beginPath()
        ctx.arc(x, y, 4, 0, Math.PI * 2)
        ctx.fill()
      }

      // Face: the contour set (jaw, brows, eyes, lips) -- readable, not a mesh.
      if (hasFace) {
        ctx.lineWidth = 1.5
        ctx.globalAlpha = 0.75
        ctx.beginPath()
        for (const { start, end } of FaceLandmarker.FACE_LANDMARKS_CONTOURS) {
          const a = data.face[start]
          const b = data.face[end]
          if (!a || !b) continue
          const [x1, y1] = at(a)
          const [x2, y2] = at(b)
          ctx.moveTo(x1, y1)
          ctx.lineTo(x2, y2)
        }
        ctx.stroke()
      }
      ctx.globalAlpha = 1
      ctx.restore()
    }
    handle = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(handle)
  }, [videoRef, frame, fit, colour])

  return <canvas ref={canvasRef} className={`pointer-events-none absolute inset-0 h-full w-full ${className}`} aria-hidden />
}

/** The reference frame nearest to `t`, from prep's overlay.json. */
export function nearestFrame(
  frames: (OverlayFrame & { t: number })[],
  t: number,
  maxGap = 0.2,
): OverlayFrame | null {
  let lo = 0
  let hi = frames.length - 1
  if (hi < 0) return null
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (frames[mid].t < t) lo = mid + 1
    else hi = mid
  }
  const best = [frames[lo], frames[lo - 1]]
    .filter(Boolean)
    .sort((a, b) => Math.abs(a.t - t) - Math.abs(b.t - t))[0]
  return best && Math.abs(best.t - t) <= maxGap ? best : null
}
