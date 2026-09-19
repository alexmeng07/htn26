import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { api, mediaUrl } from '../api/client'
import { KeypointSampler } from '../capture/keypoints'
import { useSyncedAudio } from '../capture/useSyncedAudio'
import { useRecorder } from '../capture/useRecorder'
import SkeletonOverlay, { nearestFrame, type OverlayFrame } from '../stage/SkeletonOverlay'
import { useGame } from '../store/game'

type Phase = 'arming' | 'countdown' | 'running' | 'sending' | 'error'

// Past this the landmarkers are given up on and the server extracts keypoints
// from the uploaded take instead -- slower judging, but the round still runs.
const SAMPLER_LOAD_TIMEOUT_MS = 8000
// Skeleton colours: the character in the stage spotlight, the player in cyan.
const CHARACTER_COLOUR = '#ffd76f'
const PLAYER_COLOUR = '#5ee7ff'

/**
 * The performance screen.
 *
 * Left: the target character, isolated from the movie. Right: the player.
 * Both start on the same tick, so second 14 of the take lines up with second 14
 * of the character's performance -- that is what makes the later comparison
 * possible without any alignment step. The player's pose and expression are
 * sampled live on that same clock and uploaded with the take for grading.
 *
 * While the take runs, both sides carry a live skeleton: the character's from
 * prep (overlay.json), the player's from the sampler. Drawing only, not scored.
 */
export default function Perform() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const nickname = useGame((s) => s.nickname)
  const attempt = useGame((s) => s.attempt)
  const startRound = useGame((s) => s.startRound)
  const headphones = useGame((s) => s.headphones)
  const { stream, open, start, stop, close } = useRecorder()

  const characterRef = useRef<HTMLVideoElement>(null)
  const cueRef = useRef<HTMLAudioElement>(null)
  const cameraRef = useRef<HTMLVideoElement>(null)
  const samplerRef = useRef<KeypointSampler | null>(null)
  const [phase, setPhase] = useState<Phase>('arming')
  const [count, setCount] = useState(3)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [characterFrames, setCharacterFrames] = useState<(OverlayFrame & { t: number })[]>([])
  // The cut-out is silent, so the scene's audio plays alongside it -- but only
  // into headphones. Out of speakers it would reach the mic and the voice score.
  useSyncedAudio(characterRef, cueRef, headphones)

  // Open the camera and load the landmarkers as soon as the screen mounts,
  // then count down. A landmarker failure is not fatal: see SAMPLER_LOAD_TIMEOUT_MS.
  useEffect(() => {
    let cancelled = false
    const sampler = new KeypointSampler()
    samplerRef.current = sampler
    const samplerReady = Promise.race([
      sampler.load(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), SAMPLER_LOAD_TIMEOUT_MS)),
    ]).catch((e) => console.warn('Live keypoints unavailable; the server will extract them.', e))
    Promise.all([open(), samplerReady])
      .then(() => !cancelled && setPhase('countdown'))
      .catch((e) => {
        if (cancelled) return
        setError(`Camera unavailable: ${e instanceof Error ? e.message : String(e)}`)
        setPhase('error')
      })
    return () => {
      cancelled = true
      close()
      sampler.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // The character's skeleton, precomputed in prep. Missing is fine: no overlay.
  useEffect(() => {
    if (!scene?.overlay) return
    fetch(mediaUrl(scene.overlay))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data?.frames && setCharacterFrames(data.frames))
      .catch(() => {})
  }, [scene?.overlay])
  const characterFrame = useCallback(
    () => nearestFrame(characterFrames, characterRef.current?.currentTime ?? 0),
    [characterFrames],
  )
  const playerFrame = useCallback(() => samplerRef.current?.latest ?? null, [])

  // Show the live camera feed once we have a stream.
  useEffect(() => {
    if (stream && cameraRef.current) cameraRef.current.srcObject = stream
  }, [stream])

  const begin = useCallback(async () => {
    setPhase('running')
    await start()
    const video = characterRef.current
    if (video) {
      video.currentTime = 0
      await video.play().catch(() => {})
    }
    // Stamped with the character's playback position, so sample t is reference t
    // even if playback stalls. Falls back to elapsed time if there's no video.
    const t0 = performance.now()
    const clock = video ? () => video.currentTime : () => (performance.now() - t0) / 1000
    // The sampler reads a hidden copy of the stream, never the preview on screen.
    if (stream) void samplerRef.current?.start(stream, clock)
  }, [start, stream])

  // 3-2-1, then roll both at once.
  useEffect(() => {
    if (phase !== 'countdown') return
    if (count === 0) {
      void begin()
      return
    }
    const timer = setTimeout(() => setCount((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [phase, count, begin])

  // Take over: hand it to the judges and move straight to deliberation.
  const finish = useCallback(async () => {
    const keypoints = samplerRef.current?.stop() ?? null
    const take = await stop()
    close()
    setPhase('sending')
    try {
      const { round_id } = await api.startRound(nickname || 'anonymous', attempt)
      await api.uploadTake(round_id, take, keypoints)
      startRound(round_id)
      go('deliberation')
    } catch (e) {
      setError(`Couldn't reach the judges: ${e instanceof Error ? e.message : String(e)}`)
      setPhase('error')
    }
  }, [stop, close, nickname, attempt, startRound, go])

  if (!scene) return null

  const characterSrc = mediaUrl(scene.isolated_video)

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col px-4 py-6"
    >
      <header className="mb-4 text-center">
        <p className="cv-label text-white/50">
          {scene.movie_title} — {scene.character_name}
        </p>
        <p className="mt-1 text-white/70">{scene.tip}</p>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-2">
        {/* The character, cut out of the film by SAM 2. */}
        <div className="relative overflow-hidden cv-frame bg-black">
          <span className="absolute left-3 top-3 z-10 rounded bg-black/60 px-2 py-1 text-xs text-white/70">
            {scene.character_name}
          </span>
          {characterSrc ? (
            <video
              ref={characterRef}
              src={characterSrc}
              className="h-full w-full object-contain"
              playsInline
              onTimeUpdate={(e) => {
                const v = e.currentTarget
                if (v.duration) setProgress(v.currentTime / v.duration)
              }}
              onEnded={() => void finish()}
            />
          ) : null}
          {characterSrc && scene.cue_audio && (
            <audio ref={cueRef} src={mediaUrl(scene.cue_audio)} preload="auto" />
          )}
          {characterSrc && phase === 'running' && characterFrames.length > 0 && (
            <SkeletonOverlay videoRef={characterRef} frame={characterFrame} fit="contain" colour={CHARACTER_COLOUR} />
          )}
          {!characterSrc && (
            <div className="grid h-full place-items-center p-6 text-center text-sm text-white/40">
              No isolated video for this scene yet — run
              <br />
              <code className="text-spot">make prep SCENE={scene.scene_id}</code>
            </div>
          )}
        </div>

        {/* The player. */}
        <div className="relative overflow-hidden cv-frame bg-black">
          <span className="absolute left-3 top-3 z-10 rounded bg-black/60 px-2 py-1 text-xs text-white/70">
            You
          </span>
          <video
            ref={cameraRef}
            className="h-full w-full -scale-x-100 object-cover"
            autoPlay
            playsInline
            muted
          />
          {phase === 'running' && (
            // Mirrored exactly like the preview it sits on.
            <SkeletonOverlay
              videoRef={cameraRef}
              frame={playerFrame}
              fit="cover"
              colour={PLAYER_COLOUR}
              className="-scale-x-100"
            />
          )}
          {phase === 'running' && (
            <span className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded bg-no/90 px-2 py-1 text-xs font-bold">
              <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
              REC
            </span>
          )}
        </div>
      </div>

      {/* Progress through the scene. */}
      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full bg-spot transition-[width] duration-100"
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      <footer className="mt-4 min-h-16 text-center">
        {phase === 'arming' && <p className="text-white/50">Waking the camera…</p>}
        {phase === 'countdown' && (
          <p className="text-5xl font-black text-spot">{count === 0 ? 'GO' : count}</p>
        )}
        {phase === 'running' && (
          <p className="text-white/50">
            {headphones ? 'Scene audio in your headphones. ' : 'Scene audio muted (no headphones). '}Perform.
          </p>
        )}
        {phase === 'sending' && <p className="text-spot">Cut! Sending your take to the judges…</p>}
        {phase === 'error' && (
          <div className="space-y-2">
            <p className="text-no">{error}</p>
            <button onClick={() => go('ready')} className="cv-btn-quiet bg-white/10 px-5 py-2 text-sm">
              Try again
            </button>
          </div>
        )}
      </footer>
    </motion.section>
  )
}
