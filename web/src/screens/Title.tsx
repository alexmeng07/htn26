import { useState } from 'react'
import { motion } from 'framer-motion'
import { useGame } from '../store/game'

export default function Title() {
  const scene = useGame((s) => s.scene)
  const go = useGame((s) => s.go)
  const setNickname = useGame((s) => s.setNickname)
  const [name, setName] = useState('')

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6"
    >
      <div className="w-full max-w-md text-center">
        <h1 className="text-5xl font-black tracking-tight text-spot">SceneStealer</h1>
        {/* Title line comes from the scene pack, never from a literal here. */}
        <p className="mt-3 text-lg text-white/70">{scene?.title_line ?? 'Loading scene…'}</p>

        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your nickname"
          className="mt-8 w-full rounded-lg bg-stage-deep px-4 py-3 text-center outline-none ring-1 ring-white/10 focus:ring-spot"
        />
        <button
          disabled={!name.trim() || !scene}
          onClick={() => {
            setNickname(name.trim())
            go('briefing')
          }}
          className="mt-4 w-full rounded-lg bg-spot px-4 py-3 font-bold text-stage-black disabled:opacity-40"
        >
          Start
        </button>
      </div>
    </motion.section>
  )
}
