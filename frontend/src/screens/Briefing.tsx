import { motion } from 'framer-motion'
import { useGame } from '../store/game'

/**
 * The scene card: what film, who you're playing, what to go for.
 * Everything here comes from the scene pack -- no scene text lives in code.
 */
export default function Briefing() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  if (!scene) return null

  const judged =
    scene.voice_mode === 'lines'
      ? 'Say the lines. The voice judge listens for timing and delivery.'
      : 'No lines to learn. The voice judge listens for the sounds: breaths, laughs, sobs.'

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6 py-10"
    >
      <div className="w-full max-w-xl text-center">
        <p className="text-sm uppercase tracking-widest text-white/40">{scene.movie_title}</p>
        <h2 className="mt-2 text-4xl font-black text-spot">You are {scene.character_name}</h2>
        <p className="mt-6 text-xl leading-relaxed text-white/85">{scene.briefing}</p>

        <div className="mt-8 grid gap-3 text-left sm:grid-cols-2">
          <div className="rounded-xl bg-stage-deep p-4 ring-1 ring-white/10">
            <p className="text-xs uppercase tracking-widest text-spot/80">Director's note</p>
            <p className="mt-1 text-white/80">{scene.tip}</p>
          </div>
          <div className="rounded-xl bg-stage-deep p-4 ring-1 ring-white/10">
            <p className="text-xs uppercase tracking-widest text-spot/80">How you're judged</p>
            <p className="mt-1 text-white/80">
              Face and body are measured against the original, frame by frame. {judged}
            </p>
          </div>
        </div>

        <p className="mt-6 text-sm text-white/40">
          {Math.round(scene.duration_s) || '?'} seconds
          {scene.key_moments.length > 0 && ` · ${scene.key_moments.length} key moments`}
        </p>

        <button
          onClick={() => go('watch')}
          className="mt-8 w-full rounded-lg bg-spot px-4 py-3 font-bold text-stage-black sm:w-auto sm:px-10"
        >
          Watch the scene →
        </button>
      </div>
    </motion.section>
  )
}
