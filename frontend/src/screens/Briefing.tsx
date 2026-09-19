import { motion } from 'framer-motion'
import { useGame } from '../store/game'

/** Lane B: ~10s card showing scene.briefing and scene.tip, then auto-advance. */
export default function Briefing() {
  const go = useGame((s) => s.go)
  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6 text-center"
    >
      <div>
        <h2 className="text-3xl font-bold text-spot">Briefing</h2>
        <p className="mt-3 max-w-md text-white/60">Lane B: ~10s card showing scene.briefing and scene.tip, then auto-advance.</p>
        <button
          onClick={() => go('ready')}
          className="mt-8 rounded-lg bg-white/10 px-5 py-2 text-sm"
        >
          Skip ahead →
        </button>
      </div>
    </motion.section>
  )
}
