import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { api, mediaUrl } from '../api/client'
import type { JudgeResult } from '../api/types'
import JudgeSprite, { type SpriteState } from '../stage/JudgeSprite'
import { playSfx } from '../stage/sfx'
import { useGame } from '../store/game'

type Beat = 'talking' | 'reveal'

const REVEAL_HOLD_MS = 1400
const LIP_FLAP_MS = 160
// While a judge is still deciding, check back this often, and give up after this.
const POLL_MS = 700
const WAIT_LIMIT_MS = 45_000

/** Without a voice clip, hold the bubble roughly as long as it takes to read. */
const readingTime = (text: string) => Math.max(2500, text.length * 55)

/**
 * Judges one at a time: talking sprite + voice + speech bubble, then YES or NO.
 *
 * The reveal can start before every judge has decided: face and body arrive
 * first (a partial result) while the voice is still being scored. If the reveal
 * reaches a judge who isn't ready, they sit "listening" while this screen polls
 * for the complete result, then carry on. Effects key on judge_id, so the full
 * result landing mid-speech never restarts whoever is talking.
 */
export default function Verdict() {
  const result = useGame((s) => s.result)
  const roundId = useGame((s) => s.roundId)
  const setResult = useGame((s) => s.setResult)
  const go = useGame((s) => s.go)
  const [index, setIndex] = useState(0)
  const [beat, setBeat] = useState<Beat>('talking')
  const [flap, setFlap] = useState(false)
  const [gaveUp, setGaveUp] = useState(false)

  const judges = result?.judges ?? []
  const complete = result?.complete ?? true
  const pending = result?.pending ?? []
  const waiting = !complete && index >= judges.length
  const finished = complete && index >= judges.length
  const current: JudgeResult | undefined = judges[index]
  const currentRef = useRef(current)
  currentRef.current = current
  const currentId = current?.judge_id

  // Fetch the complete result while anyone is still deciding.
  useEffect(() => {
    if (complete || !roundId) return
    let stopped = false
    const started = Date.now()
    const poll = async () => {
      while (!stopped) {
        await new Promise((r) => setTimeout(r, POLL_MS))
        if (stopped) return
        try {
          const fresh = await api.round(roundId)
          if (fresh.complete) {
            setResult(fresh)
            return
          }
        } catch {
          // A blip; keep asking until the limit.
        }
        if (Date.now() - started > WAIT_LIMIT_MS) {
          setGaveUp(true)
          return
        }
      }
    }
    void poll()
    return () => {
      stopped = true
    }
  }, [complete, roundId, setResult])

  // Talking: play the judge's line; when it ends (or the reading time runs out
  // with no audio), reveal the vote.
  useEffect(() => {
    const judge = currentRef.current
    if (!judge || beat !== 'talking') return
    let cancelled = false
    const reveal = () => !cancelled && setBeat('reveal')
    let timer: ReturnType<typeof setTimeout> | undefined
    let audio: HTMLAudioElement | undefined

    if (judge.audio_url) {
      audio = new Audio(mediaUrl(judge.audio_url))
      audio.onended = reveal
      audio.play().catch(() => {
        timer = setTimeout(reveal, readingTime(judge.spoken))
      })
    } else {
      timer = setTimeout(reveal, readingTime(judge.spoken))
    }
    const flapper = setInterval(() => setFlap((f) => !f), LIP_FLAP_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
      clearInterval(flapper)
      audio?.pause()
    }
  }, [currentId, beat])

  // Reveal: ding or buzzer, hold, then the next judge.
  useEffect(() => {
    const judge = currentRef.current
    if (!judge || beat !== 'reveal') return
    playSfx(judge.vote === 'YES' ? 'yes_ding' : 'no_buzzer')
    const timer = setTimeout(() => {
      setIndex((i) => i + 1)
      setBeat('talking')
    }, REVEAL_HOLD_MS)
    return () => clearTimeout(timer)
  }, [currentId, beat])

  // After the last judge: the crowd reacts.
  useEffect(() => {
    if (!finished || !result) return
    if (result.golden_buzzer) {
      playSfx('golden_buzzer')
      playSfx('confetti_pop')
    } else if (result.passed) {
      playSfx('applause')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished])

  if (!result) return null

  const stateFor = (j: JudgeResult, i: number): SpriteState => {
    if (i < index) return j.vote === 'YES' ? 'yes' : 'no'
    if (i > index) return 'idle'
    if (beat === 'reveal') return j.vote === 'YES' ? 'yes' : 'no'
    return flap ? 'talking' : 'idle'
  }
  const waitingFor = pending[0]

  const skip = () => {
    if (complete) go('result')
    else setIndex(judges.length) // jump past what's revealed; wait for the rest
  }

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center justify-center px-6 py-10 text-center"
    >
      {/* The speech bubble for whoever is talking -- or whoever is still deciding. */}
      <div className="mb-8 min-h-28 w-full max-w-2xl">
        <AnimatePresence mode="wait">
          {current && (
            <motion.div
              key={current.judge_id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="rounded-2xl bg-white px-6 py-4 text-left text-lg text-stage-black shadow-xl"
            >
              <p className="mb-1 text-xs font-bold uppercase tracking-widest text-stage-black/50">
                {current.name} · {current.category}
              </p>
              {/* Exactly what the voice says -- the bubble is a caption, not a paraphrase. */}
              {current.spoken}
            </motion.div>
          )}
          {waiting && waitingFor && (
            <motion.div
              key={`wait-${waitingFor.judge_id}`}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="rounded-2xl bg-white/10 px-6 py-4 text-left text-lg text-white/80"
            >
              <p className="mb-1 text-xs font-bold uppercase tracking-widest text-white/40">
                {waitingFor.name} · {waitingFor.category}
              </p>
              {gaveUp ? (
                'Lost for words tonight. Your other scores are in.'
              ) : (
                <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.4 }}>
                  Still listening back to your take…
                </motion.span>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        {finished && (
          <motion.p
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className={`text-5xl font-black ${result.golden_buzzer ? 'text-spot' : result.passed ? 'text-yes' : 'text-no'}`}
          >
            {result.golden_buzzer ? 'GOLDEN BUZZER!' : result.passed ? "You're going through!" : 'So close!'}
          </motion.p>
        )}
      </div>

      <div className="flex flex-wrap items-end justify-center gap-6 md:gap-12">
        {judges.map((j, i) => {
          const state = stateFor(j, i)
          return (
            <div key={j.judge_id} className="flex flex-col items-center gap-3">
              <JudgeSprite judgeId={j.judge_id} name={j.name} state={state} size={160} />
              <p className="text-sm text-white/60">{j.name}</p>
              <p
                className={`h-8 text-2xl font-black ${
                  state === 'yes' ? 'text-yes' : state === 'no' ? 'text-no' : 'text-transparent'
                }`}
              >
                {state === 'yes' || state === 'no' ? j.vote : '·'}
              </p>
            </div>
          )
        })}
        {pending.map((p) => (
          <div key={p.judge_id} className="flex flex-col items-center gap-3">
            {/* Deciding: idle, leaning in, a little dimmer than the rest. */}
            <motion.div
              animate={{ rotate: [-4, 4, -4] }}
              transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}
              className="opacity-80"
            >
              <JudgeSprite judgeId={p.judge_id} name={p.name} state="idle" size={160} />
            </motion.div>
            <p className="text-sm text-white/60">{p.name}</p>
            <p className="h-8 text-2xl font-black text-white/30">…</p>
          </div>
        ))}
      </div>

      {result.fallback_used && (
        <p className="mt-6 text-xs text-white/40">Some judges were on a coffee break ☕ — backup scoring used.</p>
      )}

      <button
        onClick={gaveUp ? () => go('result') : skip}
        className={`mt-8 rounded-lg px-5 py-2 text-sm ${
          finished || gaveUp ? 'bg-spot font-bold text-stage-black' : 'bg-white/5 text-white/40'
        }`}
      >
        {finished || gaveUp ? 'See your scores →' : 'Skip →'}
      </button>
    </motion.section>
  )
}
