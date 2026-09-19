import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import JudgeSprite from '../stage/JudgeSprite'
import { playSfx } from '../stage/sfx'
import { useGame } from '../store/game'

const PANEL = ['face', 'body', 'voice']
const GIVE_UP_AFTER_MS = 60_000

/** Covers the AI wait while the server streams partial and final verdict events. */
export default function Deliberation() {
  const roundId = useGame((s) => s.roundId)
  const setResult = useGame((s) => s.setResult)
  const go = useGame((s) => s.go)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!roundId) return
    const drum = playSfx('drumroll', { loop: true, volume: 0.6 })
    const events = api.events(roundId)
    let done = false

    const fail = (message: string) => {
      if (done) return
      done = true
      events.close()
      setError(message)
    }

    const reveal = async () => {
      if (done) return
      done = true
      events.close()
      try {
        setResult(await api.round(roundId))
        go('verdict')
      } catch (reason) {
        setError(`The judges lost their notes: ${reason instanceof Error ? reason.message : String(reason)}`)
      }
    }
    events.addEventListener('partial_ready', reveal)
    events.addEventListener('verdict_ready', reveal)
    events.addEventListener('error', (event) => {
      const data = (event as MessageEvent).data
      if (data) fail(`The judges walked out: ${JSON.parse(data).detail}`)
    })
    const timer = setTimeout(() => fail('The judges are taking too long.'), GIVE_UP_AFTER_MS)

    return () => {
      done = true
      clearTimeout(timer)
      events.close()
      drum.pause()
    }
  }, [roundId, setResult, go])

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6 py-10 text-center text-cream"
    >
      <div className="w-full max-w-3xl">
        <div className="mb-8 flex items-center gap-4">
          <span className="cv-tag">Panel in session</span>
          <span className="h-0.5 flex-1 bg-cream/25" />
          <span className="cv-label text-cream/65">Round {roundId?.slice(0, 6) ?? '—'}</span>
        </div>
        <div className="cv-card px-4 py-8 sm:px-8">
          <div className="flex items-end justify-center gap-3 md:gap-10">
            {PANEL.map((id, index) => (
              <motion.div
                key={id}
                animate={{ rotate: index === 1 ? [0, 2, -2, 0] : index === 0 ? [6, 9, 6] : [-6, -9, -6] }}
                transition={{ repeat: Infinity, duration: 1.2 + index * 0.3, ease: 'easeInOut' }}
                className="opacity-75"
              >
                <JudgeSprite judgeId={id} state="idle" size={140} />
              </motion.div>
            ))}
          </div>
          <hr className="cv-rule my-7" />
          {error ? (
            <div className="space-y-4">
              <p className="font-mono text-sm text-no">{error}</p>
              <button onClick={() => go('ready')} className="cv-btn bg-spot px-5 py-2 text-stage-black">
                Try again
              </button>
            </div>
          ) : (
            <div>
              <motion.p
                animate={{ opacity: [0.45, 1, 0.45] }}
                transition={{ repeat: Infinity, duration: 1.6 }}
                className="font-display text-2xl text-spot sm:text-3xl"
              >
                Deliberation in progress
              </motion.p>
              <p className="cv-label mt-3 text-cream/65">Face / body / voice · votes incoming</p>
            </div>
          )}
        </div>
      </div>
    </motion.section>
  )
}
