import type { LeaderboardEntry, RoundResult, ScenePack } from './types'

// Vite proxies /api to the FastAPI server (see vite.config.ts).
const BASE = '/api'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(json<Record<string, unknown>>),

  /** The active scene pack. Nothing else in the app knows which movie is in play. */
  scene: () => fetch(`${BASE}/scene`).then(json<ScenePack>),

  startRound: (nickname: string) => {
    const body = new FormData()
    body.append('nickname', nickname)
    return fetch(`${BASE}/rounds`, { method: 'POST', body }).then(
      json<{ round_id: string; nickname: string; scene_id: string }>,
    )
  },

  uploadTake: (roundId: string, take: Blob) => {
    const body = new FormData()
    body.append('take', take, 'take.webm')
    return fetch(`${BASE}/rounds/${roundId}/take`, { method: 'POST', body }).then(json<unknown>)
  },

  round: (roundId: string) => fetch(`${BASE}/rounds/${roundId}`).then(json<RoundResult>),

  leaderboard: () => fetch(`${BASE}/leaderboard`).then(json<LeaderboardEntry[]>),

  /** SSE: judging -> verdict_ready -> dub_ready (or error). */
  events: (roundId: string) => new EventSource(`${BASE}/rounds/${roundId}/events`),
}
