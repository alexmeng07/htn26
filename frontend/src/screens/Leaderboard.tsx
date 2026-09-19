import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import type { LeaderboardEntry } from '../api/types'
import { useGame } from '../store/game'

const REFRESH_MS = 5000
const RANK_COLORS = ['bg-spot', 'bg-yes', 'bg-no']

/** Best combined score per player for the active scene, refreshed every few seconds. */
export default function Leaderboard() {
  const scene = useGame((s) => s.scene)
  const nickname = useGame((s) => s.nickname)
  const go = useGame((s) => s.go)
  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const controller = new AbortController()

    const load = async () => {
      setRefreshing(true)
      try {
        const next = await api.leaderboard(scene?.scene_id, controller.signal)
        if (!active) return
        setEntries(next)
        setError('')
        setUpdatedAt(new Date())
      } catch (reason) {
        if (!active || (reason instanceof DOMException && reason.name === 'AbortError')) return
        setError('Live board unavailable. Scores are still saved locally.')
      } finally {
        if (active) {
          setRefreshing(false)
          // Schedule after settlement so slow requests never overlap or self-cancel.
          timer = setTimeout(() => void load(), REFRESH_MS)
        }
      }
    }

    void load()
    return () => {
      active = false
      clearTimeout(timer)
      controller.abort()
    }
  }, [scene?.scene_id, reloadKey])

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid min-h-screen place-items-center px-4 py-10 text-cream sm:px-6"
    >
      <div className="w-full max-w-3xl">
        <header className="flex flex-col gap-4 border-b-2 border-cream pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <span className="cv-tag">Live board</span>
            <h2 className="mt-3 text-4xl leading-none text-spot sm:text-6xl">Leaderboard</h2>
          </div>
          <div className="font-mono text-xs uppercase tracking-wider text-cream/65 sm:text-right">
            <p>{scene?.movie_title ?? 'Current scene'}</p>
            <p className="mt-1 text-yes">
              {refreshing ? 'Syncing…' : updatedAt ? `Updated ${updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Connecting…'}
            </p>
          </div>
        </header>

        <div aria-live="polite" className="mt-6">
          {error && (
            <div className="cv-panel mb-4 flex flex-wrap items-center justify-between gap-3 border-no px-4 py-3">
              <p className="font-mono text-sm text-no">{error}</p>
              <button onClick={() => setReloadKey((key) => key + 1)} className="cv-btn-quiet bg-stage-black px-3 py-2 text-xs">
                Retry sync
              </button>
            </div>
          )}

          {entries === null && !error && (
            <div className="cv-panel px-5 py-10 text-center">
              <p className="cv-label animate-pulse text-spot">Pulling the scores…</p>
            </div>
          )}

          {entries?.length === 0 && (
            <div className="cv-panel px-5 py-10 text-center">
              <p className="text-xl font-bold">The board is wide open.</p>
              <p className="mt-2 text-cream/65">Be the first performer to brave the stage.</p>
            </div>
          )}

          {entries && entries.length > 0 && (
            <ol className="space-y-3">
              {entries.map((entry, index) => {
                const current = entry.nickname.toLocaleLowerCase() === nickname.toLocaleLowerCase()
                return (
                  <motion.li
                    key={`${entry.nickname}-${entry.scene_id}`}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(index * 0.04, 0.3) }}
                    className={`grid grid-cols-[3rem_1fr_auto] items-stretch border-2 bg-stage-deep shadow-[5px_5px_0_rgba(0,0,0,0.65)] ${current ? 'border-spot' : 'border-cream/55'}`}
                  >
                    <span className={`cv-rank ${RANK_COLORS[index] ?? 'bg-cream/55'}`}>{String(index + 1).padStart(2, '0')}</span>
                    <span className="min-w-0 px-4 py-3">
                      <span className="flex items-center gap-2">
                        <strong className="truncate text-lg">{entry.nickname}</strong>
                        {current && <span className="cv-tag">You</span>}
                      </span>
                      <span className={`cv-label mt-1 block ${entry.passed ? 'text-yes' : 'text-cream/65'}`}>
                        {entry.passed ? 'Passed the panel' : 'Attempt logged'}
                      </span>
                    </span>
                    <span className="flex min-w-20 flex-col justify-center border-l-2 border-cream/20 px-4 text-right">
                      <strong className="font-display text-2xl text-spot">{entry.combined}</strong>
                      <span className="cv-label text-[0.58rem] text-cream/65">Score</span>
                    </span>
                  </motion.li>
                )
              })}
            </ol>
          )}
        </div>

        <footer className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t-2 border-cream/20 pt-5">
          <p className="cv-label text-cream/65">Best score per player · auto-refreshes</p>
          <button onClick={() => go('title')} className="cv-btn bg-spot px-5 py-3 text-stage-black">
            Next player →
          </button>
        </footer>
      </div>
    </motion.section>
  )
}
