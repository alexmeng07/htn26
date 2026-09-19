import { create } from 'zustand'
import type { RoundResult, ScenePack } from '../api/types'

/** The screens a round moves through, in order. */
export type Screen =
  | 'title'
  | 'briefing'
  | 'ready'
  | 'perform'
  | 'deliberation'
  | 'verdict'
  | 'result'
  | 'dub'
  | 'leaderboard'

interface GameState {
  screen: Screen
  nickname: string
  scene: ScenePack | null
  roundId: string | null
  attempt: number
  result: RoundResult | null
  go: (screen: Screen) => void
  setNickname: (nickname: string) => void
  setScene: (scene: ScenePack) => void
  startRound: (roundId: string) => void
  setResult: (result: RoundResult) => void
  retry: () => void
}

export const useGame = create<GameState>((set) => ({
  screen: 'title',
  nickname: '',
  scene: null,
  roundId: null,
  attempt: 1,
  result: null,
  go: (screen) => set({ screen }),
  setNickname: (nickname) => set({ nickname }),
  setScene: (scene) => set({ scene }),
  startRound: (roundId) => set({ roundId, result: null }),
  setResult: (result) => set({ result }),
  // Unlimited retries: keep the nickname and scene, bump the attempt counter.
  retry: () => set((s) => ({ screen: 'ready', attempt: s.attempt + 1, result: null })),
}))
