import { useState } from 'react'
import { motion } from 'framer-motion'
import { useGame } from '../store/game'

const MAX_NICKNAME_LENGTH = 24

export default function Title() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const setNickname = useGame((s) => s.setNickname)
  const [name, setName] = useState('')
  const nickname = name.trim()

  const enter = () => {
    if (!nickname || !scene) return
    setNickname(nickname)
    go('briefing')
  }

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6 py-10 text-cream"
    >
      <div className="w-full max-w-xl">
        <div className="cv-card relative px-6 py-8 md:px-10 md:py-10">
          <span className="cv-tag absolute -top-4 left-5">One take only</span>
          <p className="cv-label text-yes">Performance simulator / 001</p>
          <h1 className="mt-4 text-6xl leading-[0.82] text-spot sm:text-7xl">
            LARP<br /><span className="text-cream">SIM</span>
          </h1>
          {/* Deliberately generic: the scene remains a surprise until Briefing. */}
          <p className="mt-6 max-w-md border-l-4 border-no pl-4 text-lg leading-relaxed text-cream/75">
            {scene ? 'One movie scene. One take. Three very honest judges.' : 'Loading the stage…'}
          </p>

          <form
            className="mt-8 border-t-2 border-cream/20 pt-6"
            onSubmit={(event) => {
              event.preventDefault()
              enter()
            }}
          >
            <label htmlFor="nickname" className="cv-label block text-cream/65">
              Stage name <span className="text-no">*</span>
            </label>
            <input
              id="nickname"
              autoComplete="nickname"
              maxLength={MAX_NICKNAME_LENGTH}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="TYPE YOUR NICKNAME"
              className="cv-input mt-3 w-full px-4 py-3 outline-none"
            />
            <div className="mt-2 flex justify-between font-mono text-[0.65rem] uppercase tracking-wider text-cream/65">
              <span>Shown on the live board</span>
              <span>{name.length}/{MAX_NICKNAME_LENGTH}</span>
            </div>
            <button
              type="submit"
              disabled={!nickname || !scene}
              className="cv-btn mt-5 w-full bg-spot px-4 py-3 text-stage-black disabled:cursor-not-allowed disabled:opacity-40"
            >
              Enter the stage →
            </button>
          </form>
        </div>
      </div>
    </motion.section>
  )
}
