import { motion } from 'framer-motion'
import type { Category } from '../api/types'
import { useGame } from '../store/game'

const LABEL: Record<Category, string> = { face: 'Face', body: 'Body', voice: 'Voice' }

/** Final scorecard, notes, and routes into retry, replay, or leaderboard. */
export default function Result() {
  const result = useGame((s) => s.result)
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const retry = useGame((s) => s.retry)
  if (!result) return null

  const noJudges = result.judges.filter((judge) => judge.vote === 'NO')

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-4 py-10 text-cream sm:px-6"
    >
      <div className="w-full max-w-3xl">
        <header className="grid gap-5 border-b-2 border-cream pb-6 sm:grid-cols-[1fr_auto] sm:items-end">
          <div>
            <span className={`cv-tag ${result.passed ? 'bg-yes text-stage-black' : 'bg-no'}`}>
              {result.passed ? 'Panel approved' : 'Attempt complete'}
            </span>
            <h2 className={`mt-3 text-4xl leading-none sm:text-5xl ${result.golden_buzzer ? 'text-spot' : result.passed ? 'text-yes' : 'text-no'}`}>
              {result.golden_buzzer ? 'Golden buzzer!' : result.passed ? "You're going through!" : 'So close!'}
            </h2>
            <p className="mt-3 font-mono text-sm uppercase tracking-wider text-cream/65">
              {result.nickname} · attempt {result.attempt}
            </p>
          </div>
          <div className="border-2 border-spot bg-spot px-5 py-3 text-center text-stage-black shadow-[5px_5px_0_#e85b46]">
            <strong className="block font-display text-4xl">{result.combined}</strong>
            <span className="cv-label text-[0.62rem]">Combined</span>
          </div>
        </header>

        <div className="cv-panel mt-6 divide-y-2 divide-cream/15 px-5">
          {result.judges.map((judge) => {
            const threshold = scene?.thresholds[judge.category]
            return (
              <div key={judge.judge_id} className="py-4">
                <div className="flex items-end justify-between gap-4">
                  <span>
                    <strong className="text-lg">{LABEL[judge.category]}</strong>
                    <span className="ml-2 text-sm text-cream/65">/ {judge.name}</span>
                  </span>
                  <span className={`cv-label text-right ${judge.vote === 'YES' ? 'text-yes' : 'text-no'}`}>
                    {judge.score} · {judge.vote}
                    {threshold != null && <span className="block text-cream/65">Pass mark {threshold}</span>}
                  </span>
                </div>
                <div
                  className="cv-meter relative mt-3"
                  role="meter"
                  aria-label={`${LABEL[judge.category]} score`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={judge.score}
                  aria-valuetext={`${judge.score} out of 100${threshold != null ? `; pass mark ${threshold}` : ''}`}
                >
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${judge.score}%` }}
                    transition={{ duration: 0.8 }}
                    className={`h-full ${judge.vote === 'YES' ? 'bg-yes' : 'bg-no'}`}
                  />
                  {threshold != null && (
                    <span aria-hidden="true" className="absolute top-0 h-full w-0.5 bg-cream" style={{ left: `${threshold}%` }} />
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {(result.best_moment || result.worst_moment) && (
          <div className="mt-5 grid gap-4 text-sm md:grid-cols-2">
            {result.best_moment && (
              <div className="cv-panel border-yes p-4">
                <p className="cv-label text-yes">Best moment / {result.best_moment.t.toFixed(1)}s</p>
                <p className="mt-2 text-cream/75">{result.best_moment.matched || result.best_moment.missed}</p>
              </div>
            )}
            {result.worst_moment && (
              <div className="cv-panel border-no p-4">
                <p className="cv-label text-no">Needs work / {result.worst_moment.t.toFixed(1)}s</p>
                <p className="mt-2 text-cream/75">{result.worst_moment.missed || result.worst_moment.matched}</p>
              </div>
            )}
          </div>
        )}

        {noJudges.length > 0 && (
          <div className="mt-5 border-l-4 border-spot bg-spot/10 p-4 text-sm">
            <p className="cv-label mb-3 text-spot">Notes from the panel</p>
            <div className="space-y-2">
              {noJudges.map((judge) => (
                <p key={judge.judge_id}><strong>{judge.name}:</strong> <span className="text-cream/70">{judge.tip}</span></p>
              ))}
            </div>
          </div>
        )}

        <footer className="mt-7 flex flex-wrap gap-3 border-t-2 border-cream/20 pt-5">
          <button onClick={retry} className="cv-btn bg-spot px-5 py-3 text-stage-black">Try again</button>
          <button onClick={() => go('dub')} className="cv-btn-quiet bg-stage-deep px-5 py-3">Watch replay</button>
          <button onClick={() => go('leaderboard')} className="cv-btn-quiet bg-stage-deep px-5 py-3">Leaderboard →</button>
        </footer>
      </div>
    </motion.section>
  )
}
