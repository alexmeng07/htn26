/** Mirrors server/schemas.py and server/scene.py. Keep the two in step. */

export type Category = 'face' | 'body' | 'voice'
export type Vote = 'YES' | 'NO'

export interface KeyMoment {
  t: number
  label: string
  face: string
  body: string
  voice: string
}

export interface ScenePack {
  scene_id: string
  movie_title: string
  character_name: string
  actor_name: string
  briefing: string
  tip: string
  title_line: string
  voice_mode: 'emotional' | 'lines'
  other_voices_in_audio: boolean
  thresholds: { face: number; body: number; voice: number }
  isolated_video: string
  cue_audio: string
  subtitles: string
  duration_s: number
  key_moments: KeyMoment[]
}

export interface MomentNote {
  t: number
  matched: string
  missed: string
}

export interface JudgeResult {
  judge_id: string
  name: string
  category: Category
  vote: Vote
  score: number
  spoken: string
  bubble: string
  tip: string
  audio_url: string | null
}

export interface RoundResult {
  round_id: string
  nickname: string
  attempt: number
  scene_id: string
  face: number
  body: number
  voice: number
  combined: number
  judges: JudgeResult[]
  best_moment: MomentNote | null
  worst_moment: MomentNote | null
  passed: boolean
  golden_buzzer: boolean
  dub_url: string | null
  fallback_used: boolean
}

export interface LeaderboardEntry {
  nickname: string
  combined: number
  scene_id: string
  passed: boolean
}
