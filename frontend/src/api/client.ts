import type { KeypointTimeline, LeaderboardEntry, RoundResult, ScenePack } from './types'

// Vite proxies /api to the FastAPI server (see vite.config.ts).
const BASE = '/api'

/**
 * Scene media (isolated video, cue audio, masks) comes back from /scene as a
 * server-rooted path like "/media/<scene>/isolated.mp4". Prefix it so the
 * browser goes through the same proxy as the rest of the API.
 */
export const mediaUrl = (path: string) => (path ? `${BASE}${path}` : '')

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(json<Record<string, unknown>>),

  /** The active scene pack. Nothing else in the app knows which movie is in play. */
  scene: () => fetch(`${BASE}/scene`).then(json<ScenePack>),

  startRound: (nickname: string, attempt = 1) => {
    const body = new FormData()
    body.append('nickname', nickname)
    body.append('attempt', String(attempt))
    return fetch(`${BASE}/rounds`, { method: 'POST', body }).then(
      json<{ round_id: string; nickname: string; scene_id: string }>,
    )
  },

  /** The take, plus the keypoints sampled live (null -> the server extracts them). */
  uploadTake: (roundId: string, take: Blob, keypoints: KeypointTimeline | null = null) => {
    const body = new FormData()
    body.append('take', take, 'take.webm')
    if (keypoints) {
      body.append('keypoints', new Blob([JSON.stringify(keypoints)], { type: 'application/json' }), 'keypoints.json')
    }
    return fetch(`${BASE}/rounds/${roundId}/take`, { method: 'POST', body }).then(json<unknown>)
  },

  round: (roundId: string) => fetch(`${BASE}/rounds/${roundId}`).then(json<RoundResult>),

  leaderboard: (sceneId?: string) =>
    fetch(`${BASE}/leaderboard${sceneId ? `?scene_id=${encodeURIComponent(sceneId)}` : ''}`).then(
      json<LeaderboardEntry[]>,
    ),

  /** SSE: judging -> verdict_ready -> dub_ready (or error). */
  events: (roundId: string) => new EventSource(`${BASE}/rounds/${roundId}/events`),
}
