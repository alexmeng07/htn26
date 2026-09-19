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
const POLL_MS = 700
const WAIT_LIMIT_MS = 45_000
const readingTime = (text: string) => Math.max(2500, text.length * 55)

/** Reveals each judge's spoken line and vote while late scoring continues. */
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

  useEffect(() => {
    if (complete || !roundId) return
    let stopped = false
    const started = Date.now()
    const poll = async () => {
      while (!stopped) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS))
        if (stopped) return
        try {
          const fresh = await api.round(roundId)
          if (fresh.complete) {
            setResult(fresh)
            return
          }
        } catch {
          // Keep asking through transient network failures.
        }
        if (Date.now() - started > WAIT_LIMIT_MS) {
          setGaveUp(true)
          return
        }
      }
    }
    void poll()
    return () => { stopped = true }
  }, [complete, roundId, setResult])

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
      audio.play().catch(() => { timer = setTimeout(reveal, readingTime(judge.spoken)) })
    } else {
      timer = setTimeout(reveal, readingTime(judge.spoken))
    }
    const flapper = setInterval(() => setFlap((value) => !value), LIP_FLAP_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
      clearInterval(flapper)
      audio?.pause()
    }
  }, [currentId, beat])

  useEffect(() => {
    const judge = currentRef.current
    if (!judge || beat !== 'reveal') return
    playSfx(judge.vote === 'YES' ? 'yes_ding' : 'no_buzzer')
    const timer = setTimeout(() => {
      setIndex((value) => value + 1)
      setBeat('talking')
    }, REVEAL_HOLD_MS)
    return () => clearTimeout(timer)
  }, [currentId, beat])

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

  const stateFor = (judge: JudgeResult, judgeIndex: number): SpriteState => {
    if (judgeIndex < index) return judge.vote === 'YES' ? 'yes' : 'no'
    if (judgeIndex > index) return 'idle'
    if (beat === 'reveal') return judge.vote === 'YES' ? 'yes' : 'no'
    return flap ? 'talking' : 'idle'
  }
  const waitingFor = pending[0]
  const skip = () => complete ? go('result') : setIndex(judges.length)

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center justify-center px-4 py-10 text-center text-cream sm:px-6"
    >
      <div className="w-full max-w-5xl">
        <header className="mb-6 flex items-center gap-4 border-b-2 border-cream pb-4 text-left">
          <span className="cv-tag">The verdict</span>
          <span className="h-0.5 flex-1 bg-cream/20" />
          <span className="cv-label text-cream/65">Judge {Math.min(index + 1, 3)} / 3</span>
        </header>

        <div className="mx-auto mb-8 min-h-32 w-full max-w-3xl">
          <AnimatePresence mode="wait">
            {current && (
              <motion.div
                key={current.judge_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                className="cv-card px-6 py-5 text-left"
              >
                <p className="cv-label mb-2 text-yes">{current.name} / {current.category}</p>
                <p className="text-lg leading-relaxed text-cream">{current.spoken}</p>
              </motion.div>
            )}
            {waiting && waitingFor && (
              <motion.div
                key={`wait-${waitingFor.judge_id}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                className="cv-panel border-spot px-6 py-5 text-left"
              >
                <p className="cv-label mb-2 text-spot">{waitingFor.name} / {waitingFor.category}</p>
                {gaveUp ? (
                  <p className="text-cream/70">Lost for words tonight. Your other scores are in.</p>
                ) : (
                  <motion.p animate={{ x: [0, 3, 0] }} transition={{ repeat: Infinity, duration: 1.4 }} className="text-cream/70">
                    Still listening back to your take…
                  </motion.p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          {finished && (
            <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="border-y-2 border-cream py-5">
              <p className={`font-display text-4xl sm:text-6xl ${result.golden_buzzer ? 'text-spot' : result.passed ? 'text-yes' : 'text-no'}`}>
                {result.golden_buzzer ? 'Golden buzzer!' : result.passed ? "You're going through!" : 'So close!'}
              </p>
            </motion.div>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          {judges.map((judge, judgeIndex) => {
            const state = stateFor(judge, judgeIndex)
            const revealed = state === 'yes' || state === 'no'
            return (
              <div key={judge.judge_id} className={`cv-panel flex min-w-0 flex-col items-center p-4 ${revealed ? state === 'yes' ? 'border-yes' : 'border-no' : ''}`}>
                <JudgeSprite judgeId={judge.judge_id} name={judge.name} state={state} size={160} />
                <p className="mt-3 font-bold">{judge.name}</p>
                <p className={`cv-label mt-2 min-h-6 ${state === 'yes' ? 'text-yes' : state === 'no' ? 'text-no' : 'text-cream/65'}`}>
                  {revealed ? judge.vote : beat === 'talking' && judgeIndex === index ? 'Speaking' : 'Waiting'}
                </p>
              </div>
            )
          })}
          {pending.map((judge) => (
            <div key={judge.judge_id} className="cv-panel flex min-w-0 flex-col items-center p-4 opacity-80">
              <motion.div animate={{ rotate: [-4, 4, -4] }} transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}>
                <JudgeSprite judgeId={judge.judge_id} name={judge.name} state="idle" size={160} />
              </motion.div>
              <p className="mt-3 font-bold">{judge.name}</p>
              <p className="cv-label mt-2 min-h-6 text-cream/65">Deciding…</p>
            </div>
          ))}
        </div>

        {result.fallback_used && (
          <p className="cv-label mt-5 text-cream/65">Backup scoring active / all votes still count</p>
        )}

        <button
          onClick={gaveUp ? () => go('result') : skip}
          className={`mt-7 px-5 py-3 ${finished || gaveUp ? 'cv-btn bg-spot text-stage-black' : 'cv-btn-quiet bg-stage-deep text-cream/65'}`}
        >
          {finished || gaveUp ? 'See your scores →' : 'Skip reveal →'}
        </button>
      </div>
    </motion.section>
  )
}
