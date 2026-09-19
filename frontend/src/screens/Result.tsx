import { motion } from 'framer-motion'
import type { Category } from '../api/types'
import { useGame } from '../store/game'

const LABEL: Record<Category, string> = { face: 'Face', body: 'Body', voice: 'Voice' }

/** Three YESes means "You're going through!". Otherwise "So close!" plus the NO judges' tips. */
export default function Result() {
  const result = useGame((s) => s.result)
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const retry = useGame((s) => s.retry)
  if (!result) return null

  const noJudges = result.judges.filter((j) => j.vote === 'NO')

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6 py-10"
    >
      <div className="w-full max-w-xl text-center">
        <h2
          className={`text-4xl font-black ${result.golden_buzzer ? 'text-spot' : result.passed ? 'text-yes' : 'text-no'}`}
        >
          {result.passed ? "You're going through!" : 'So close!'}
        </h2>
        <p className="mt-2 text-white/60">
          {result.nickname} · attempt {result.attempt} · combined{' '}
          <span className="font-bold text-white">{result.combined}</span>
        </p>

        <div className="mt-8 space-y-3 text-left">
          {result.judges.map((j) => {
            const threshold = scene?.thresholds[j.category]
            return (
              <div key={j.judge_id}>
                <div className="flex justify-between text-sm">
                  <span>
                    {LABEL[j.category]} <span className="text-white/40">· {j.name}</span>
                  </span>
                  <span className={j.vote === 'YES' ? 'text-yes' : 'text-no'}>
                    {j.score} {j.vote}
                  </span>
                </div>
                <div className="relative mt-1 h-2 overflow-hidden rounded-full bg-white/10">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${j.score}%` }}
                    transition={{ duration: 0.8 }}
                    className={`h-full ${j.vote === 'YES' ? 'bg-yes' : 'bg-no'}`}
                  />
                  {threshold != null && (
                    // The bar a judge needed to clear.
                    <span className="absolute top-0 h-full w-0.5 bg-white/70" style={{ left: `${threshold}%` }} />
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {(result.best_moment || result.worst_moment) && (
          <div className="mt-6 grid gap-3 text-left text-sm md:grid-cols-2">
            {result.best_moment && (
              <div className="rounded-lg bg-yes/10 p-3">
                <p className="text-xs uppercase tracking-widest text-yes">
                  Best · {result.best_moment.t.toFixed(1)}s
                </p>
                <p className="mt-1 text-white/80">{result.best_moment.matched || result.best_moment.missed}</p>
              </div>
            )}
            {result.worst_moment && (
              <div className="rounded-lg bg-no/10 p-3">
                <p className="text-xs uppercase tracking-widest text-no">
                  Worst · {result.worst_moment.t.toFixed(1)}s
                </p>
                <p className="mt-1 text-white/80">{result.worst_moment.missed || result.worst_moment.matched}</p>
              </div>
            )}
          </div>
        )}

        {noJudges.length > 0 && (
          <div className="mt-6 space-y-2 text-left text-sm">
            {noJudges.map((j) => (
              <p key={j.judge_id} className="rounded-lg bg-white/5 p-3">
                <span className="font-bold text-spot">{j.name}:</span> {j.tip}
              </p>
            ))}
          </div>
        )}

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <button onClick={retry} className="cv-btn bg-spot px-5 py-2 font-bold text-stage-black">
            Try again
          </button>
          <button onClick={() => go('dub')} className="cv-btn-quiet bg-white/10 px-5 py-2">
            Watch the replay
          </button>
          <button onClick={() => go('leaderboard')} className="cv-btn-quiet bg-white/10 px-5 py-2">
            Leaderboard
          </button>
        </div>
      </div>
    </motion.section>
  )
}
