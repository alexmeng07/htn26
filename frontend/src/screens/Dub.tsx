import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { api, mediaUrl } from '../api/client'
import SkeletonOverlay, { nearestFrame, type OverlayFrame } from '../stage/SkeletonOverlay'
import { useGame } from '../store/game'

// Same colours as during the take: the character in the spotlight, the player in cyan.
const CHARACTER_COLOUR = '#ffd76f'
const PLAYER_COLOUR = '#5ee7ff'

type Frames = (OverlayFrame & { t: number })[]

async function loadFrames(url: string): Promise<Frames> {
  const res = await fetch(mediaUrl(url))
  if (!res.ok) return []
  return ((await res.json())?.frames ?? []) as Frames
}

const POLL_MS = 1500
const GIVE_UP_AFTER_MS = 45_000

/**
 * The replay: the player composited into the scene in place of the character
 * (side-by-side when the scene has no masks), with the voice-changed audio once
 * the dub is ready.
 *
 * Skeletons toggle on to show both performances at once, in the replay's own
 * frame: the character's points (from prep) where the character actually was,
 * the player's points (from the compositor) on the player -- so the gap between
 * the two is the difference in movement. Only offered on the overlay replay.
 */
export default function Dub() {
  const result = useGame((s) => s.result)
  const scene = useGame((s) => s.scene)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [skeletons, setSkeletons] = useState(false)
  const [characterFrames, setCharacterFrames] = useState<Frames>([])
  const [playerFrames, setPlayerFrames] = useState<Frames>([])
  const setResult = useGame((s) => s.setResult)
  const go = useGame((s) => s.go)
  const [gaveUp, setGaveUp] = useState(false)
  const dubUrl = result?.dub_url

  // The dub lands a few seconds after the verdict; poll until it does.
  useEffect(() => {
    if (!result || dubUrl) return
    const started = Date.now()
    const timer = setInterval(async () => {
      if (Date.now() - started > GIVE_UP_AFTER_MS) {
        clearInterval(timer)
        setGaveUp(true)
        return
      }
      const fresh = await api.round(result.round_id).catch(() => null)
      if (fresh?.dub_url) {
        clearInterval(timer)
        setResult(fresh)
      }
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [result, dubUrl, setResult])

  const overlayUrl = result?.replay_overlay
  useEffect(() => {
    if (!skeletons || !overlayUrl) return
    if (!playerFrames.length) void loadFrames(overlayUrl).then(setPlayerFrames).catch(() => {})
    if (!characterFrames.length && scene?.overlay)
      void loadFrames(scene.overlay).then(setCharacterFrames).catch(() => {})
  }, [skeletons, overlayUrl, scene?.overlay, playerFrames.length, characterFrames.length])
  const characterFrame = useCallback(
    () => nearestFrame(characterFrames, videoRef.current?.currentTime ?? 0),
    [characterFrames],
  )
  const playerFrame = useCallback(
    () => nearestFrame(playerFrames, videoRef.current?.currentTime ?? 0, 0.1),
    [playerFrames],
  )

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center justify-center px-4 py-8"
    >
      <h2 className="mb-4 text-2xl font-bold text-spot">The replay</h2>
      <div className="relative aspect-video w-full max-w-5xl overflow-hidden cv-frame bg-black">
        {dubUrl ? (
          <video ref={videoRef} src={mediaUrl(dubUrl)} className="h-full w-full object-contain" controls autoPlay playsInline />
        ) : (
          <div className="grid h-full place-items-center text-white/50">
            {gaveUp ? 'The replay reel jammed.' : 'Rolling the tape…'}
          </div>
        )}
        {skeletons && characterFrames.length > 0 && (
          <SkeletonOverlay videoRef={videoRef} frame={characterFrame} fit="contain" colour={CHARACTER_COLOUR} />
        )}
        {skeletons && playerFrames.length > 0 && (
          <SkeletonOverlay videoRef={videoRef} frame={playerFrame} fit="contain" colour={PLAYER_COLOUR} />
        )}
      </div>

      {dubUrl && overlayUrl && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 text-sm">
          <button
            onClick={() => setSkeletons((on) => !on)}
            aria-pressed={skeletons}
            className={`px-4 py-2 ${
              skeletons ? 'cv-btn bg-cream text-stage-black' : 'cv-btn-quiet bg-white/5 text-white/80'
            }`}
          >
            {skeletons ? 'Hide skeletons' : 'Show skeletons'}
          </button>
          {skeletons && (
            <span className="flex items-center gap-4 text-white/70">
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: CHARACTER_COLOUR }} />
                {scene?.character_name ?? 'Original'}
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: PLAYER_COLOUR }} />
                You
              </span>
            </span>
          )}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <button onClick={() => go('result')} className="cv-btn-quiet bg-white/10 px-5 py-2">
          ← Scores
        </button>
        <button
          onClick={() => go('leaderboard')}
          className="cv-btn bg-spot px-5 py-2 font-bold text-stage-black"
        >
          Leaderboard →
        </button>
      </div>
    </motion.section>
  )
}
