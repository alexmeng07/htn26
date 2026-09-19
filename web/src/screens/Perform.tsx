import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { mediaUrl } from '../api/client'
import { useRecorder } from '../capture/useRecorder'
import { useGame } from '../store/game'

type Phase = 'arming' | 'countdown' | 'running' | 'done' | 'error'

/**
 * The performance screen.
 *
 * Left: the target character, isolated from the movie. Right: the player.
 * Both start on the same tick, so second 14 of the take lines up with second 14
 * of the character's performance -- that is what makes the later comparison
 * possible without any alignment step.
 */
export default function Perform() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const { stream, open, start, stop, close } = useRecorder()

  const characterRef = useRef<HTMLVideoElement>(null)
  const cameraRef = useRef<HTMLVideoElement>(null)
  const [phase, setPhase] = useState<Phase>('arming')
  const [count, setCount] = useState(3)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [takeSize, setTakeSize] = useState<number | null>(null)

  // Open the camera as soon as the screen mounts, then count down.
  useEffect(() => {
    let cancelled = false
    open()
      .then(() => !cancelled && setPhase('countdown'))
      .catch((e) => {
        if (cancelled) return
        setError(`Camera unavailable: ${e instanceof Error ? e.message : String(e)}`)
        setPhase('error')
      })
    return () => {
      cancelled = true
      close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
  }, [start])

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

  const finish = useCallback(async () => {
    const take = await stop()
    setTakeSize(take.size)
    setPhase('done')
    close()
  }, [stop, close])

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
        <p className="text-sm uppercase tracking-widest text-white/40">
          {scene.movie_title} — {scene.character_name}
        </p>
        <p className="mt-1 text-white/70">{scene.tip}</p>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-2">
        {/* The character, cut out of the film by SAM 2. */}
        <div className="relative overflow-hidden rounded-xl bg-black ring-1 ring-white/10">
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
          ) : (
            <div className="grid h-full place-items-center p-6 text-center text-sm text-white/40">
              No isolated video for this scene yet — run
              <br />
              <code className="text-spot">make prep SCENE={scene.scene_id}</code>
            </div>
          )}
        </div>

        {/* The player. */}
        <div className="relative overflow-hidden rounded-xl bg-black ring-1 ring-white/10">
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
            {scene.other_voices_in_audio ? 'Headphones on. ' : ''}Perform.
          </p>
        )}
        {phase === 'done' && (
          <div className="space-y-2">
            <p className="text-yes">
              Take captured{takeSize ? ` (${(takeSize / 1_000_000).toFixed(1)} MB)` : ''}.
            </p>
            <button
              onClick={() => go('deliberation')}
              className="rounded-lg bg-spot px-5 py-2 font-bold text-stage-black"
            >
              Continue →
            </button>
          </div>
        )}
        {phase === 'error' && <p className="text-no">{error}</p>}
      </footer>
    </motion.section>
  )
}
