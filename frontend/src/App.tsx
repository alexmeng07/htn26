import { useEffect } from 'react'
import { AnimatePresence } from 'framer-motion'
import { api } from './api/client'
import { useGame } from './store/game'
import Title from './screens/Title'
import Briefing from './screens/Briefing'
import Watch from './screens/Watch'
import Ready from './screens/Ready'
import Perform from './screens/Perform'
import Deliberation from './screens/Deliberation'
import Verdict from './screens/Verdict'
import Result from './screens/Result'
import Dub from './screens/Dub'
import Leaderboard from './screens/Leaderboard'

const SCREENS = {
  title: Title,
  briefing: Briefing,
  watch: Watch,
  ready: Ready,
  perform: Perform,
  deliberation: Deliberation,
  verdict: Verdict,
  result: Result,
  dub: Dub,
  leaderboard: Leaderboard,
}

export default function App() {
  const screen = useGame((s) => s.screen)
  const setScene = useGame((s) => s.setScene)
  const Current = SCREENS[screen]

  // Load the active scene pack once. Every piece of scene-specific text in the
  // UI comes from here -- never from a literal in a component.
  useEffect(() => {
    api.scene().then(setScene).catch(() => {})
  }, [setScene])

  return (
    <main className="min-h-full bg-stage-black text-white">
      <AnimatePresence mode="wait">
        <Current key={screen} />
      </AnimatePresence>
    </main>
  )
}
