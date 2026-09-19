import { create } from 'zustand'
import type { RoundResult, ScenePack } from '../api/types'

/** The screens a round moves through, in order. */
export type Screen =
  | 'title'
  | 'briefing'
  | 'watch'
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
  /** Confirmed on Ready. Without headphones the scene audio is muted during the
   *  take, so the film's voices can't bleed into the mic and the voice score. */
  headphones: boolean
  go: (screen: Screen) => void
  setNickname: (nickname: string) => void
  setScene: (scene: ScenePack) => void
  startRound: (roundId: string) => void
  setResult: (result: RoundResult) => void
  setHeadphones: (headphones: boolean) => void
  retry: () => void
}

export const useGame = create<GameState>((set) => ({
  screen: 'title',
  nickname: '',
  scene: null,
  roundId: null,
  attempt: 1,
  result: null,
  headphones: false,
  go: (screen) => set({ screen }),
  setNickname: (nickname) => set({ nickname }),
  setScene: (scene) => set({ scene }),
  startRound: (roundId) => set({ roundId, result: null }),
  setResult: (result) => set({ result }),
  setHeadphones: (headphones) => set({ headphones }),
  // Unlimited retries: keep the nickname and scene, bump the attempt counter.
  retry: () => set((s) => ({ screen: 'ready', attempt: s.attempt + 1, result: null })),
}))
