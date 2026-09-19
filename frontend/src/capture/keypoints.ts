import { FaceLandmarker, PoseLandmarker } from '@mediapipe/tasks-vision'
import wasmLoaderPath from '@mediapipe/tasks-vision/vision_wasm_internal.js?url'
import wasmBinaryPath from '@mediapipe/tasks-vision/vision_wasm_internal.wasm?url'
import { mediaUrl } from '../api/client'
import type { KeypointSample, KeypointTimeline } from '../api/types'
import type { OverlayFrame } from '../stage/SkeletonOverlay'

/**
 * Samples the player's pose and facial expression live during the take.
 *
 * Same MediaPipe version and the SAME pinned model files that prep ran over the
 * reference clip (served from /models, so it works offline) -- that is what
 * makes the two timelines comparable. The WASM runtime is bundled by Vite.
 *
 * Timestamps come from the CHARACTER VIDEO's playback position, not wall time.
 * The player copies what they see, so if playback stalls for a moment the
 * player stalls with it -- a wall clock would then drift away from the
 * reference and every later sample would be compared against the wrong beat.
 * If anything here fails, the take uploads without keypoints and the server
 * extracts them from the video instead -- the round never depends on this.
 *
 * Why the preview doesn't freeze: detection reads from a hidden <video> of the
 * same camera stream, never the one on screen, and the GPU models are warmed
 * up on a blank frame during load -- the first real inference would otherwise
 * compile shaders mid-take and stall the page for a second or more.
 */

const SAMPLE_FPS = 15
const round = (v: number, places: number) => Math.round(v * 10 ** places) / 10 ** places

type FrameVideo = HTMLVideoElement & {
  requestVideoFrameCallback?: (cb: () => void) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

export class KeypointSampler {
  private pose: PoseLandmarker | null = null
  private face: FaceLandmarker | null = null
  private samples: KeypointSample[] = []
  private video: FrameVideo | null = null
  private clock: () => number = () => 0
  private last = -Infinity
  private lastStamp = 0
  private handle = 0
  private running = false
  /** The most recent detection, for drawing the player's skeleton. */
  latest: OverlayFrame | null = null

  /** Load both landmarkers and warm them up. Rejects if the browser can't run them. */
  async load(): Promise<void> {
    const fileset = { wasmLoaderPath, wasmBinaryPath }
    const [pose, face] = await Promise.all([
      PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: mediaUrl('/models/pose_landmarker_full.task'), delegate: 'GPU' },
        runningMode: 'VIDEO',
        numPoses: 1,
      }),
      FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: mediaUrl('/models/face_landmarker.task'), delegate: 'GPU' },
        runningMode: 'VIDEO',
        numFaces: 1,
        outputFaceBlendshapes: true,
      }),
    ])
    // Warm-up: pay the shader compilation now, before the countdown.
    const blank = document.createElement('canvas')
    blank.width = 256
    blank.height = 144
    blank.getContext('2d')?.fillRect(0, 0, 256, 144)
    for (let i = 0; i < 2; i++) {
      this.lastStamp += 1
      pose.detectForVideo(blank, this.lastStamp)
      face.detectForVideo(blank, this.lastStamp)
    }
    this.pose = pose
    this.face = face
  }

  get ready() {
    return this.pose !== null && this.face !== null
  }

  /**
   * Begin sampling the camera `stream`. `clock` returns the current position in
   * the scene in seconds -- the character video's currentTime.
   */
  async start(stream: MediaStream, clock: () => number) {
    if (!this.ready) return
    const video: FrameVideo = document.createElement('video')
    video.muted = true
    video.playsInline = true
    // Attached but invisible: some browsers throttle detached video elements.
    video.style.cssText = 'position:fixed;left:0;top:0;width:2px;height:2px;opacity:0;pointer-events:none'
    video.srcObject = stream
    document.body.appendChild(video)
    await video.play().catch(() => {})
    this.video = video
    this.clock = clock
    this.samples = []
    this.latest = null
    this.last = -Infinity
    this.running = true
    this.schedule()
  }

  private schedule() {
    const video = this.video
    if (!this.running || !video) return
    // Only run on NEW camera frames where the browser can tell us about them.
    if (video.requestVideoFrameCallback) this.handle = video.requestVideoFrameCallback(this.tick)
    else this.handle = requestAnimationFrame(this.tick)
  }

  private tick = () => {
    const video = this.video
    if (!this.running || !video) return
    const now = performance.now()
    if (now - this.last >= 1000 / SAMPLE_FPS && video.readyState >= 2) {
      this.last = now
      // detectForVideo needs strictly increasing timestamps.
      const stamp = Math.max(Math.round(now), this.lastStamp + 1)
      this.lastStamp = stamp
      try {
        const pose = this.pose!.detectForVideo(video, stamp)
        const face = this.face!.detectForVideo(video, stamp)
        const posePoints = pose.landmarks[0] ?? []
        const facePoints = face.faceLandmarks[0] ?? []
        this.samples.push({
          t: round(this.clock(), 3),
          pose: posePoints.map((p) => ({
            x: round(p.x, 4),
            y: round(p.y, 4),
            z: round(p.z, 4),
            visibility: round(p.visibility ?? 0, 3),
          })),
          face: Object.fromEntries(
            (face.faceBlendshapes[0]?.categories ?? []).map((c) => [c.categoryName, round(c.score, 4)]),
          ),
        })
        this.latest = {
          pose: posePoints.map((p) => [p.x, p.y, p.visibility ?? 0]),
          face: facePoints.map((p) => [p.x, p.y]),
        }
      } catch {
        // One bad frame is not worth the take; the next tick tries again.
      }
    }
    this.schedule()
  }

  private cancel() {
    const video = this.video
    if (video?.cancelVideoFrameCallback) video.cancelVideoFrameCallback(this.handle)
    else cancelAnimationFrame(this.handle)
  }

  /** Stop and return the timeline, or null if nothing usable was captured. */
  stop(): KeypointTimeline | null {
    this.running = false
    this.cancel()
    const video = this.video
    this.video = null
    this.latest = null
    if (!video) return null
    const aspect = video.videoWidth / video.videoHeight || 16 / 9
    video.srcObject = null
    video.remove()
    if (this.samples.length === 0) return null
    const elapsed = this.samples[this.samples.length - 1].t || 1
    return { fps: round(this.samples.length / elapsed, 2), aspect: round(aspect, 4), samples: this.samples }
  }

  close() {
    if (this.running) this.stop()
    this.pose?.close()
    this.face?.close()
    this.pose = this.face = null
  }
}
