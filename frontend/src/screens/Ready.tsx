import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useRecorder } from '../capture/useRecorder'
import { useGame } from '../store/game'

type Check = 'asking' | 'ok' | 'denied' | 'missing' | 'busy' | 'failed'

/** Why getUserMedia failed, in words a stranger at a booth can act on (R5.7). */
function explain(error: unknown): Check {
  const name = error instanceof DOMException ? error.name : ''
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'denied'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'missing'
  if (name === 'NotReadableError' || name === 'AbortError') return 'busy'
  return 'failed'
}

const HELP: Record<Exclude<Check, 'asking' | 'ok'>, { title: string; body: string }> = {
  denied: {
    title: 'Camera or microphone was blocked',
    body: 'Click the camera icon in the address bar, allow both camera and microphone, then try again.',
  },
  missing: {
    title: 'No camera or microphone found',
    body: 'Plug one in (or check it is enabled in system settings), then try again.',
  },
  busy: {
    title: 'The camera is in use by another app',
    body: 'Close any video call or camera app, then try again.',
  },
  failed: {
    title: "Couldn't start the camera",
    body: 'Try again. If it keeps failing, reload the page.',
  },
}

/**
 * Pre-flight: camera and mic permission (with a retry that never dead-ends the
 * player), a framing guide, and the headphones check. The countdown itself
 * lives on Perform, where recording starts.
 */
export default function Ready() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const headphones = useGame((s) => s.headphones)
  const setHeadphones = useGame((s) => s.setHeadphones)
  const { stream, open, close } = useRecorder()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [check, setCheck] = useState<Check>('asking')

  const ask = useCallback(() => {
    setCheck('asking')
    open()
      .then(() => setCheck('ok'))
      .catch((e) => setCheck(explain(e)))
  }, [open])

  useEffect(() => {
    ask()
    // Perform opens its own stream; release this one on the way out.
    return close
  }, [ask, close])
  useEffect(() => {
    if (stream && videoRef.current) videoRef.current.srcObject = stream
  }, [stream])

  if (!scene) return null
  const needsHeadphones = scene.other_voices_in_audio
  const canStart = check === 'ok' && (headphones || !needsHeadphones)

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center px-4 py-6"
    >
      <h2 className="text-2xl font-bold text-spot">Get in position</h2>
      <p className="mt-1 text-white/60">Frame yourself like the character: head and shoulders inside the guide.</p>

      <div className="relative mt-4 aspect-video w-full max-w-3xl overflow-hidden cv-frame bg-black">
        <video ref={videoRef} className="h-full w-full -scale-x-100 object-cover" autoPlay playsInline muted />
        {check === 'ok' && (
          // Head-and-shoulders guide. Framing is a nudge here, never a score (R6.14).
          <svg viewBox="0 0 160 90" className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
            <ellipse cx="80" cy="36" rx="17" ry="22" fill="none" stroke="rgba(255,215,111,.7)" strokeWidth=".6" strokeDasharray="2 1.5" />
            <path d="M40 90 C44 70 60 62 80 62 C100 62 116 70 120 90" fill="none" stroke="rgba(255,215,111,.7)" strokeWidth=".6" strokeDasharray="2 1.5" />
          </svg>
        )}
        {check === 'asking' && (
          <div className="absolute inset-0 grid place-items-center text-white/60">Asking for camera and microphone…</div>
        )}
        {check !== 'asking' && check !== 'ok' && (
          <div className="absolute inset-0 grid place-items-center p-6 text-center">
            <div>
              <p className="text-lg font-bold text-no">{HELP[check].title}</p>
              <p className="mt-2 max-w-md text-white/70">{HELP[check].body}</p>
              <button onClick={ask} className="mt-4 cv-btn-quiet bg-white/15 px-5 py-2 text-sm">
                Try again
              </button>
            </div>
          </div>
        )}
      </div>

      <label className="mt-5 flex max-w-3xl cursor-pointer items-start gap-3 cv-card p-4">
        <input
          type="checkbox"
          checked={headphones}
          onChange={(e) => setHeadphones(e.target.checked)}
          className="mt-1 h-4 w-4 accent-[var(--color-spot)]"
        />
        <span className="text-sm text-white/80">
          <strong className="text-white">I'm wearing headphones.</strong>{' '}
          {needsHeadphones
            ? 'Required for this scene: other voices in the film would leak into your microphone.'
            : "You'll hear the scene while you perform. Without them it plays silently, so the film can't leak into your mic."}
        </span>
      </label>

      <button
        disabled={!canStart}
        onClick={() => go('perform')}
        className="mt-6 cv-btn bg-spot px-10 py-3 font-bold text-stage-black disabled:opacity-40"
      >
        {check === 'ok' && needsHeadphones && !headphones ? 'Headphones on to start' : 'Start — 3, 2, 1'}
      </button>
      <button onClick={() => go('watch')} className="mt-3 text-sm text-white/50 underline-offset-4 hover:underline">
        ← Watch the scene again
      </button>
    </motion.section>
  )
}
