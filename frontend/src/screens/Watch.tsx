import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { mediaUrl } from '../api/client'
import type { KeyMoment } from '../api/types'
import { useSyncedAudio } from '../capture/useSyncedAudio'
import { useGame } from '../store/game'

// A key moment's card shows from this long before it until this long after.
const LEAD_S = 1.2
const HOLD_S = 1.0

/**
 * Study the character before performing: the cut-out plays on its own with the
 * scene's audio, and each key moment's reference notes (written once in prep)
 * come up as it arrives -- the same beats the judges will be watching for.
 */
export default function Watch() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const videoRef = useRef<HTMLVideoElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const [time, setTime] = useState(0)
  const [ended, setEnded] = useState(false)
  useSyncedAudio(videoRef, audioRef)

  if (!scene) return null
  const src = mediaUrl(scene.isolated_video || scene.cue_audio)
  const duration = scene.duration_s || 1
  const moments = scene.key_moments
  // Windows can overlap when moments are close; the nearest one wins.
  const current: KeyMoment | undefined = moments
    .filter((m) => time >= m.t - LEAD_S && time <= m.t + HOLD_S)
    .sort((a, b) => Math.abs(a.t - time) - Math.abs(b.t - time))[0]

  const replay = () => {
    const video = videoRef.current
    if (!video) return
    setEnded(false)
    video.currentTime = 0
    void video.play()
  }

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center px-4 py-6"
    >
      <header className="mb-4 text-center">
        <p className="text-sm uppercase tracking-widest text-white/40">Study the scene</p>
        <h2 className="mt-1 text-2xl font-bold text-spot">{scene.character_name}</h2>
      </header>

      <div className="relative w-full max-w-4xl overflow-hidden rounded-xl bg-black ring-1 ring-white/10">
        {src ? (
          <video
            ref={videoRef}
            src={src}
            className="aspect-video w-full object-contain"
            autoPlay
            playsInline
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            onEnded={() => setEnded(true)}
          />
        ) : (
          <div className="grid aspect-video place-items-center p-6 text-sm text-white/40">
            No clip for this scene yet — run <code className="text-spot">make prep</code>
          </div>
        )}
        {/* The cut-out is silent; the scene's own audio rides alongside it. */}
        {scene.isolated_video && scene.cue_audio && (
          <audio ref={audioRef} src={mediaUrl(scene.cue_audio)} preload="auto" />
        )}

        {current && (current.face || current.voice) && (
          <motion.div
            key={current.t}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="absolute inset-x-3 bottom-3 rounded-lg bg-black/75 p-3 text-sm backdrop-blur"
          >
            <p className="text-xs uppercase tracking-widest text-spot">Key moment · {current.t.toFixed(1)}s</p>
            {current.face && <p className="mt-1 text-white/90">Face: {current.face}</p>}
            {current.voice && <p className="text-white/70">Voice: {current.voice}</p>}
          </motion.div>
        )}
      </div>

      {/* Timeline with the key moments marked. */}
      <div className="relative mt-4 h-2 w-full max-w-4xl rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-spot/70 transition-[width] duration-100"
          style={{ width: `${Math.min(100, (time / duration) * 100)}%` }}
        />
        {moments.map((m) => (
          <span
            key={m.t}
            title={`${m.t.toFixed(1)}s`}
            className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-stage-black ${
              current?.t === m.t ? 'bg-spot' : 'bg-white/50'
            }`}
            style={{ left: `${(m.t / duration) * 100}%` }}
          />
        ))}
      </div>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button onClick={replay} className="rounded-lg bg-white/10 px-5 py-2.5 text-sm">
          ↺ Watch again
        </button>
        <button
          onClick={() => go('ready')}
          className={`rounded-lg px-6 py-2.5 font-bold text-stage-black ${ended ? 'bg-spot' : 'bg-spot/70'}`}
        >
          I'm ready →
        </button>
      </div>
    </motion.section>
  )
}
