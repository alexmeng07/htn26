import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import JudgeSprite from '../stage/JudgeSprite'
import { playSfx } from '../stage/sfx'
import { useGame } from '../store/game'

// The panel, left to right. Names arrive with the result; ids are enough here.
const PANEL = ['face', 'body', 'voice']
const GIVE_UP_AFTER_MS = 60_000

/**
 * Lights dim, the judges lean in and whisper, drumroll. This covers the AI wait.
 *
 * The server streams `partial_ready` once face and body are judged and voiced
 * (a few seconds), and `verdict_ready` when the voice judge is in too. Whichever
 * comes first starts the reveal; Verdict waits for the rest if it needs to.
 */
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
      } catch (e) {
        setError(`The judges lost their notes: ${e instanceof Error ? e.message : String(e)}`)
      }
    }
    events.addEventListener('partial_ready', reveal)
    events.addEventListener('verdict_ready', reveal)
    events.addEventListener('error', (e) => {
      // Server-sent `error` events carry JSON; a dropped connection does not.
      const data = (e as MessageEvent).data
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
      className="grid min-h-screen place-items-center bg-black px-6 text-center"
    >
      <div>
        <div className="flex items-end justify-center gap-6 md:gap-10">
          {PANEL.map((id, i) => (
            <motion.div
              key={id}
              // Lean toward the middle judge, with a small whisper wobble.
              animate={{ rotate: i === 1 ? [0, 2, -2, 0] : i === 0 ? [6, 9, 6] : [-6, -9, -6] }}
              transition={{ repeat: Infinity, duration: 1.2 + i * 0.3, ease: 'easeInOut' }}
              className="opacity-70"
            >
              <JudgeSprite judgeId={id} state="idle" size={140} />
            </motion.div>
          ))}
        </div>
        {error ? (
          <div className="mt-10 space-y-3">
            <p className="text-no">{error}</p>
            <button
              onClick={() => go('ready')}
              className="rounded-lg bg-spot px-5 py-2 font-bold text-stage-black"
            >
              Try again
            </button>
          </div>
        ) : (
          <motion.p
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ repeat: Infinity, duration: 1.6 }}
            className="mt-10 text-2xl font-bold text-spot"
          >
            The judges are deliberating…
          </motion.p>
        )}
      </div>
    </motion.section>
  )
}
