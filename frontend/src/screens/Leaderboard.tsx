import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import type { LeaderboardEntry } from '../api/types'
import { useGame } from '../store/game'

const REFRESH_MS = 5000

/** Best combined score per player for the active scene, refreshed every few seconds. */
export default function Leaderboard() {
  const scene = useGame((s) => s.scene)
  const nickname = useGame((s) => s.nickname)
  const go = useGame((s) => s.go)
  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null)

  useEffect(() => {
    const load = () => api.leaderboard(scene?.scene_id).then(setEntries).catch(() => {})
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [scene?.scene_id])

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-6 py-10"
    >
      <div className="w-full max-w-md text-center">
        <h2 className="text-3xl font-black text-spot">Leaderboard</h2>
        <ol className="mt-6 space-y-2 text-left">
          {entries === null && <li className="text-center text-white/40">Loading…</li>}
          {entries?.length === 0 && (
            <li className="text-center text-white/40">No one has braved the stage yet.</li>
          )}
          {entries?.map((e, i) => (
            <li
              key={e.nickname}
              className={`flex items-center justify-between rounded-lg px-4 py-2 ${
                e.nickname === nickname ? 'bg-spot/15 ring-1 ring-spot' : 'bg-white/5'
              }`}
            >
              <span>
                <span className="mr-3 inline-block w-6 text-white/40">{i + 1}</span>
                {e.nickname}
                {e.passed && <span className="ml-2 text-xs text-yes">✓</span>}
              </span>
              <span className="font-bold">{e.combined}</span>
            </li>
          ))}
        </ol>
        <button onClick={() => go('title')} className="mt-8 rounded-lg bg-white/10 px-5 py-2">
          Next player
        </button>
      </div>
    </motion.section>
  )
}
