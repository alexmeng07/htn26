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
  overlay: string // URL of the character's skeleton points for the take ('' before prep)
  cue_audio: string
  subtitles: string
  duration_s: number
  key_moments: KeyMoment[]
}

/** Mirrors KeypointTimeline in server/schemas.py: the browser's side of grading. */
export interface PoseLandmark {
  x: number
  y: number
  z: number
  visibility: number
}

export interface KeypointSample {
  t: number // seconds since the take started, on the recording clock
  pose: PoseLandmark[] // 33 points, or empty when no person was found
  face: Record<string, number> // blendshape name -> 0..1
}

export interface KeypointTimeline {
  fps: number
  aspect: number // frame width / height
  samples: KeypointSample[]
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

/** A judge still deciding (the voice judge while the voice is scored). */
export interface JudgeStub {
  judge_id: string
  name: string
  category: Category
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
  /** The player's skeleton on the replay; null if the replay is the side-by-side. */
  replay_overlay: string | null
  /** Original-clip vs microphone loudness for the replay; null if unavailable. */
  waveforms: string | null
  fallback_used: boolean
  /** false: face and body are in and can be revealed; `pending` is still coming. */
  complete: boolean
  pending: JudgeStub[]
}

export interface LeaderboardEntry {
  nickname: string
  combined: number
  scene_id: string
  passed: boolean
}
