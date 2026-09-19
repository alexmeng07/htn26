# LARPsim — Requirements

**Spec:** `larpsim` · **Repo:** `htn26` · **Event:** Hack the North 2026
**Goal:** one live-demoable round of LARPsim, end to end, on the demo laptop, within 16 hours.

> **Supersedes** `.kiro/specs/scenestealer-demo/`, which was written before the grading model and
> architecture were settled. Where `HANDOFF.md` disagrees with this document, this document wins.

---

## Introduction

LARPsim is a performance game. The player acts out one character from a real film or TV scene. The
character plays back beside the player's live camera. When the scene ends, the player's **body pose
and facial expression are compared geometrically** against the character's, their **voice is judged
by a multimodal model**, plain code turns those scores into three YES/NO votes, an LLM writes three
judge reactions that match those votes, and a speech service performs them AGT-style. Three YESes
and the player passes. Afterwards they get a replay with their voice transformed and the character
cut out of the film — purely for fun.

The repository already contains the route contract, every data shape, the scene-pack model, the
vote rules, the ffmpeg helpers, and a complete SAM 2 Truss. What it lacks is a working round and,
now, an entire grading subsystem.

---

## Naming

**I8 governs this and is not negotiable.**

| Layer | Name |
|---|---|
| Product, UI copy, docs, README, Devpost, spec files | **LARPsim** |
| Python package, module paths, class names, env var names, MongoDB database, FastAPI internals, repo directory | **scenestealer** / unchanged |

The rename is a **presentation-layer change only**. Renaming `server/`, `MONGODB_DB=scenestealer`,
or any `*_API_KEY` would break working configuration and credentials for no benefit. Anything a
judge or player reads says LARPsim; anything a machine reads is untouched.

---

## Ground truth (verified)

Confirmed by reading the repo and probing the machine on 2026-09-19.

### Baseline — done and green

| Tool | Version | Note |
|---|---|---|
| uv | 0.12.17 | winget |
| Node | 24.19.0 | **portable zip**; the winget MSI needs admin and stalled on an unanswerable UAC prompt |
| pnpm | 12.4.2 | Corepack fails with EPERM against `C:\Program Files\nodejs`; installed into a user-writable npm prefix instead |
| ffmpeg | 4.4 | already present |
| Python | 3.11.1 | venv, matching the `>=3.11,<3.13` pin |

pytest 16 passed · ruff clean · pnpm install 182 packages · tsc clean · vitest 4 passed ·
`GET /health` 200, reporting the three `VOICE_JUDGE_*` IDs as the only missing credentials.

Two Node 24.19.0 installs now exist (Program Files and `~\tools`). Both work; consolidating needs
one elevated install and is cosmetic.

### Code that works

Paths below are relative to `backend/` for Python and `frontend/` for the React app.

`server/config.py` · `server/scene.py` · `server/schemas.py` · `server/rules/votes.py` ·
`server/media/ffmpeg.py` · `server/judges/personas.py` · `server/main.py` routes ·
`prep/trim.py` · `prep/isolate_client.py` · `infra/truss/sam2/model/model.py` (never run on a GPU) ·
`server/compare/omni.py` prompt builder · `frontend/` router, store, API client, recorder,
`Perform` and `Title` screens.

### Code that is stubbed

`prep/keyframes.py` · `prep/annotate_reference.py` · `prep/build_pack.py` ·
`compare/omni.py::compare` · `compare/fallback.py` · `judges/writer.py` (×3) ·
`voice/speech.py` (×4) · `store/db.py` (×2) · `round/pipeline.py` ·
`POST /rounds/{id}/take` (HTTP 501) · seven placeholder web screens.

### Facts that shape this spec

1. **No grading subsystem exists at all.** Nothing in the repo extracts or compares keypoints. This
   is the single largest piece of new work.
2. **The source clip is now in place** at `assets/private/test-scene-1/test_clip_1.mp4` (2.1 MB),
   which is the path `scenes/test-scene-1/scene.yaml` points at. Scene Prep has still never run,
   so no `pack.json` exists yet.
3. **A scene is chosen**, contradicting `HANDOFF.md`. `scenes/test-scene-1/scene.yaml` selects
   *The Bear* / Carmy / Jeremy Allen White, `voice_mode: lines`, `other_voices_in_audio: false`,
   thresholds face 70 / body 45 / voice 65, box `[227, 0, 1160, 720]` in 1280×720, duration 10.4 s.
   `ACTIVE_SCENE=test-scene-1`.
4. **A close-up scene has almost no body in frame.** The configured body threshold of 45 already
   acknowledges this. Pose grading must degrade gracefully when only head and shoulders are visible.
5. **All credentials are present** except the three ElevenLabs judge voice IDs.
6. **No judge sprites exist**, and no cached SFX or fallback lines. The team may supply sprites.
7. **The Baseten SAM 2 endpoint is unverified.** It is now needed only for the fun overlay, which
   demotes it from blocking to optional.
8. **No numpy, OpenCV, or MediaPipe is currently a project dependency.** Keypoint grading requires
   adding them.

---

## Invariants

Hold for every requirement. A change violating one is wrong even if its own criteria pass.

- **I1 — No hardcoded scene details.** No film title, character, actor, line, timestamp, or clip
  filename in any source file, prompt, or UI string. All of it comes from the scene pack. Swapping
  scenes means re-running prep and changing `ACTIVE_SCENE`, nothing else.
- **I2 — Votes are decided in code.** Only the rules module decides YES/NO. Identical inputs always
  produce an identical verdict.
- **I3 — Face and body scores are deterministic and geometric.** They come from measured keypoints,
  never from a language model. Running the same take twice yields the same face and body score.
- **I4 — Voices are designed, never cloned** from the actor or any real person.
- **I5 — Copyrighted media never enters git.** Clips stay under gitignored `assets/private/`.
- **I6 — The demo survives a dead network.** A complete round remains playable offline.
- **I7 — Contracts are extended, not redefined.** The documented routes and the shapes in
  `server/schemas.py` are the integration contract; additions are additive.
- **I8 — LARPsim is the product name; `scenestealer` remains every internal identifier.**
- **I9 — Segmentation is cosmetic.** SAM 2 masks feed the replay overlay only. No score depends on
  them, and a segmentation failure cannot change a verdict.

---

## Requirements

### R1 — A runnable local baseline · P0 · **done**

**User story:** As a developer, I want one command to install everything and run the tests.

1. WHEN setup is run on this machine THEN all Python and Node dependencies SHALL install without
   manual intervention.
2. The setup path SHALL NOT require administrator rights.
3. WHEN setup completes THEN pytest, ruff, tsc, and vitest SHALL all pass.
4. WHEN the API is started THEN `GET /health` SHALL return 200 and report per-service readiness.
5. IF a required tool cannot be installed THEN the failure SHALL name the tool and the reason.

### R2 — Product rename to LARPsim · P0

**User story:** As a judge at the event, I want to see one consistent product name.

1. Every user-visible surface — window title, title screen, README heading, spec documents, Devpost
   copy — SHALL read **LARPsim**.
2. Python packages, module paths, environment-variable names, the MongoDB database name, and
   credential values SHALL remain unchanged.
3. WHEN the rename is complete THEN the test suite and `GET /health` SHALL still pass, proving no
   internal identifier moved.
4. No user-visible string SHALL read "SceneStealer" except where deliberately describing project
   history.

### R3 — An architecture several developers can work in at once · P0

**User story:** As one of several developers, I want to build my slice without waiting for, or
breaking, anyone else's.

1. The repo SHALL be split into `backend/` (Python) and `frontend/` (React), with shared data
   (`scenes/`, `assets/`) at the top level. Within `backend/server/`, the existing one-module-per-
   concern layout (`compare/`, `rules/`, `judges/`, `voice/`, `store/`, `round/`, `media/`) SHALL be
   kept as-is — no api/services/domain/adapters layering.
2. Each subsystem — grading, judges, voice, scene, store, round — SHALL be reachable through its own
   HTTP surface, so a developer can exercise it standalone without the rest of the pipeline working.
3. Every module that calls an external system SHALL support a fallback or fake path selectable
   without code changes, so any lane can be developed and tested with no credentials and no network.
4. Scoring and vote logic SHALL contain no HTTP, file, or network access, and SHALL be unit-testable
   without fixtures.
5. WHEN the restructure lands THEN every existing import path that tests or code already use SHALL
   keep working, and the documented routes SHALL behave identically (**I7**).
6. The architecture SHALL remain a single deployable process per half. Splitting a subsystem out
   later is explicitly out of scope.
7. Directory layout SHALL be documented so a new contributor can find their lane without asking.

### R4 — Scene Prep produces a complete scene pack · P0

**User story:** As an operator, I want one command to turn a raw clip into everything the game needs.

1. WHEN prep is run for a scene with a present source clip THEN it SHALL execute every stage in order
   and write `scenes/<id>/pack.json`.
2. Each stage SHALL write a discrete artifact and SHALL skip itself when that artifact already
   exists, so a late failure never forces re-running an expensive earlier stage.
3. WHEN the trim stage runs THEN it SHALL produce a clip normalised to a consistent height and frame
   rate, cut to the configured start and end.
4. WHEN the source clip is missing THEN prep SHALL fail immediately, naming the exact expected path
   and any near-miss files it found.
5. WHERE the configured clip filename does not exist but exactly one video file is present in the
   scene's private directory, the system SHALL use it and say loudly that it did so.
6. WHEN the keypoint stage runs THEN it SHALL extract per-frame body pose and facial-expression data
   for the target character across the whole clip and store it in the pack (see R6).
7. WHEN the key-moment stage runs THEN it SHALL select between 6 and 10 moments spread across the
   clip, preferring points where pose or expression changes most.
8. WHERE the clip is too short to yield 6 distinct moments the system SHALL select as many as the
   duration supports and SHALL warn rather than fail.
9. WHEN the reference-sheet stage runs THEN it SHALL make exactly one multimodal-model call for the
   whole clip and populate face, body, and voice prose for every key moment, for the judges to quote.
10. WHEN the reference sheet succeeds THEN it SHALL be cached, and re-running prep SHALL NOT repeat
    the call unless forced.
11. WHEN the pack is built THEN it SHALL validate against the scene-pack model, record duration and a
    prepared-at stamp, and upsert to MongoDB.
12. IF MongoDB is unreachable THEN prep SHALL still write the local pack and SHALL warn.
13. WHEN two scenes have been prepped THEN switching the active scene SHALL change every
    scene-specific string and media path with no code edit (verifies **I1**).
14. The segmentation stage SHALL be optional: IF it fails or is skipped THEN prep SHALL still produce
    a pack sufficient for a complete graded round (verifies **I9**).

### R5 — The performance is captured in sync · P0

**User story:** As a player, I want to watch the character and be recorded at the same time.

1. WHEN the performance starts THEN the character video and the recorder SHALL begin on the same
   tick, so time *t* in the take corresponds to time *t* in the reference.
2. WHEN the character video ends THEN recording SHALL stop and the take SHALL be uploaded.
3. The recording SHALL capture the player's camera and microphone only, never the scene audio.
4. WHILE the player performs THEN their body pose and facial expression SHALL be sampled live in the
   browser and timestamped against the same clock as the recording.
5. WHEN the take is uploaded THEN the sampled keypoint timeline SHALL be uploaded with it.
6. WHERE the scene requires headphones the UI SHALL gate the countdown on confirmation.
7. IF camera or microphone access is denied THEN a recoverable error SHALL be shown.
8. IF live sampling is unavailable in the player's browser THEN the system SHALL fall back to
   extracting keypoints server-side from the uploaded take, and the round SHALL still complete.
9. WHILE the player performs THEN a skeleton or mesh overlay MAY be drawn for feel, and SHALL NOT
   affect scoring.

### R6 — Face and body are graded geometrically · P0

**User story:** As a player, I want my score to reflect how closely my actual posture and expression
matched the character's, and to be the same every time for the same performance.

1. Body scoring SHALL compare body-pose keypoints; face scoring SHALL compare facial-expression
   measures. Neither SHALL be produced by a language model (**I3**).
2. Pose comparison SHALL be invariant to the player's position in frame, their distance from the
   camera, and their body proportions, so that a correct pose at a different scale still scores well.
   Camera framing SHALL NOT enter the pose comparison; where framing is scored at all it is a separate
   component (R6.14).
3. Facial comparison SHALL use person-invariant expression measures rather than raw landmark
   positions, so that a different face making the same expression scores well.
4. Reference and player keypoints SHALL be produced by the same model family and the same
   normalisation, so the two are genuinely comparable.
5. Comparison SHALL tolerate small timing differences, matching within a bounded window either side
   of each reference timestamp rather than requiring exact frame alignment.
6. Scoring SHALL weight the scene's key moments more heavily than ordinary frames.
7. **The reference defines the comparison scope.** WHEN grading a frame THEN the system SHALL
   determine which body parts are actually visible in the *reference* and SHALL compare only those,
   against the same named points on the player. Body parts the reference does not show SHALL be
   excluded rather than scored as mismatches, and body parts the player shows but the reference does
   not SHALL be ignored rather than penalised. A close-up that shows only head, neck and shoulders is
   therefore graded on head, neck and shoulders. WHERE that visible region is small the system SHALL
   derive its measures from that region rather than collapsing to a single coarse signal (R6.15).
8. IF no person is detected in a reference frame THEN that frame SHALL be excluded from scoring.
9. IF no person is detected in the player's data for a substantial share of the take THEN the report
   SHALL flag the player as not visible.
10. IF the player is silent for a substantial share of the take THEN the report SHALL flag it.
11. WHEN grading completes THEN it SHALL produce a 0–100 score per category, a short human-readable
    reason, per-moment notes, and the best and worst moment with timestamps.
12. Running the same take and the same pack twice SHALL produce identical face and body scores
    (verifies **I3**).
13. Grading SHALL complete well inside the round's time budget and SHALL require no network.
14. **Framing is scored separately from pose, or not at all.** WHERE the player is far closer to or
    further from the camera than the reference framing implies, the system MAY apply a small, clearly
    labelled framing adjustment, and SHALL keep it out of the pose comparison so that R6.2's scale
    invariance still holds. A framing adjustment SHALL NOT be able to change a vote on its own.
15. **Thin evidence is reported, not hidden.** WHEN the reference's visible region yields few
    comparable measures THEN the report SHALL carry a count of the measures actually used, so the UI
    and the judges' lines can acknowledge what could and could not be seen.

### R7 — Voice is judged by a multimodal model · P0

**User story:** As a player, I want my delivery judged by something that can actually hear me.

1. WHEN a take is received THEN the system SHALL build one side-by-side video with the character on
   the left, the player on the right, frame-synced, carrying the player's audio only.
2. WHEN the comparison runs THEN the system SHALL make one multimodal call and SHALL validate the
   reply against the comparison-report model before any downstream use.
3. The call SHALL receive the reference sheet, so its judgement is grounded in the character's
   actual delivery at each moment.
4. WHERE the scene's voice mode is line-based the voice score SHALL reflect words, timing, and
   intonation; WHERE it is emotional it SHALL reflect vocal delivery rather than line accuracy.
5. The model SHALL also return qualitative per-moment notes, which the judges use for specificity.
6. IF the reply is malformed THEN the system SHALL retry once and fall back on a second failure.
7. IF the call exceeds its time budget THEN the system SHALL abandon it and fall back.
8. The model SHALL be selectable between a cheaper development model and the demo model without a
   code change, to protect the credit cap.
9. The model SHALL NOT set the face or body score (**I3**).

### R8 — Three judges vote, and code decides · P0

1. Each judge SHALL vote YES if and only if their category score meets their threshold.
2. Thresholds SHALL come from the scene pack, falling back to the configured default only where the
   pack sets none.
3. WHEN all three vote YES THEN the round SHALL pass; otherwise it SHALL fail.
4. WHEN all three scores reach the golden-buzzer level THEN the verdict SHALL be flagged as such.
5. The same report and pack SHALL always produce the same verdict (verifies **I2**).

### R9 — The judges react in character · P0

1. WHEN a verdict is decided THEN all three judges' lines SHALL be produced in a single structured
   call, validated against the judge-lines model.
2. Each line SHALL include a spoken reaction, a longer speech-bubble version, and a coaching tip.
3. Each reaction SHALL be consistent with the vote it was handed; a NO SHALL NOT read as praise.
4. Each reaction SHALL reference at least one concrete moment.
5. Reactions SHALL roast the performance, SHALL NOT comment on the player's appearance or identity,
   and SHALL stay PG-13.
6. Personas SHALL load from the judge asset files and SHALL NOT impersonate a real talent-show judge.
7. IF the call fails or returns invalid output THEN pre-written lines SHALL be served, selected by
   judge, vote, and score band.
8. Pre-written lines SHALL exist on disk for every such combination.

### R10 — The judges are heard · P1

1. WHEN judge lines are ready THEN speech SHALL be synthesised in each judge's own designed voice.
2. Synthesis SHALL be staged so the first judge can begin speaking before the others are complete.
3. Three judge voices SHALL be designed once from text descriptions, their IDs stored in
   configuration, after which `GET /health` SHALL report no missing credentials.
4. Sound effects for drumroll, YES, NO, applause, and golden buzzer SHALL be generated once, cached,
   and reused without further calls.
5. IF synthesis fails THEN the verdict SHALL still play with speech bubbles and cached audio.
6. Voices SHALL be designed, never cloned (**I4**).

### R11 — One round runs end to end · P0

1. WHEN a take is uploaded THEN the route SHALL accept it, return promptly, and run the pipeline in
   the background.
2. WHILE the pipeline runs THEN it SHALL emit judging, then verdict-ready, then replay-ready, and an
   error event on unrecoverable failure.
3. WHEN the verdict is ready THEN the round route SHALL return a complete result: scores, per-judge
   votes and lines, audio links, best and worst moments, pass state, and the fallback flag.
4. The wait between the take ending and the first judge speaking SHALL be covered by the
   deliberation animation, and SHALL be measured and logged rather than assumed.
5. WHEN a round finishes THEN the result SHALL be persisted.
6. WHEN the player retries THEN the attempt counter SHALL increment and nickname and scene SHALL
   persist.
7. IF any stage fails unrecoverably THEN an error event SHALL be emitted rather than hanging.
8. WHERE take deletion is configured the raw take SHALL be deleted once scoring completes, unless the
   replay was kept.

### R12 — The verdict is a show · P0

1. WHEN deliberation begins THEN the stage SHALL dim, the judges SHALL animate as if conferring, and
   a drumroll SHALL play.
2. WHEN the verdict plays THEN judges SHALL deliver one at a time with a talking animation, a speech
   bubble, their voice, then a YES or NO reveal and its sound effect.
3. Judge sprites SHALL animate from four states each: idle, talking, yes, no.
4. WHERE sprite artwork is absent the system SHALL render an obvious placeholder set of the same
   dimensions, and real art SHALL drop in with no code change.
5. WHEN a round passes THEN the result screen SHALL celebrate; WHEN it fails THEN it SHALL offer Try
   Again and show a tip from a judge who voted NO.
6. WHEN the verdict is a golden buzzer THEN a distinct celebration SHALL play.
7. Every scene-specific string SHALL come from the scene pack (verifies **I1**).

### R13 — The replay, for fun · P2

**User story:** As a player, I want a clip worth showing people.

1. WHEN a round is scored THEN the system SHALL produce a replay of the performance with the player's
   audio transformed into a voice designed from the scene pack's dub style.
2. The replay SHALL be produced in parallel with judging and SHALL NOT delay the verdict.
3. WHERE segmentation masks exist the replay MAY composite the player into the scene in place of the
   character; otherwise it SHALL fall back to the side-by-side view.
4. No part of the replay SHALL influence any score (verifies **I9**).
5. IF the replay fails THEN the verdict SHALL be unaffected and the screen SHALL be skippable.

### R14 — Scores are remembered · P2

1. WHEN a round completes THEN the result SHALL be written to MongoDB and mirrored locally.
2. WHEN the leaderboard is requested THEN it SHALL return the best combined score per nickname for the
   active scene, ranked, honouring the limit.
3. IF MongoDB is unreachable THEN the leaderboard SHALL serve from the local mirror and the round
   SHALL NOT fail.
4. The leaderboard screen SHALL reflect newly finished rounds without a manual reload.

### R15 — Nothing takes the demo down · P1

1. WHERE forced-fallback mode is enabled the system SHALL bypass every external call and complete a
   full round from local assets.
2. IF the multimodal model is unavailable THEN the voice score SHALL degrade to a local signal-based
   estimate, and face and body SHALL be unaffected because they are already local (**I3**).
3. IF the line writer is unavailable THEN pre-written lines SHALL be used.
4. IF speech synthesis is unavailable THEN cached audio and speech bubbles SHALL be used.
5. WHEN any fallback is used THEN the result SHALL flag it and the UI SHALL show a light-hearted
   notice.
6. WHEN the network is disabled entirely THEN a complete round SHALL still be playable, verified by an
   explicit rehearsal (verifies **I6**).
7. WHERE the player has no headphones the scene audio SHALL be muted and subtitles shown.

### R16 — The project is presentable and honest · P2

1. The README SHALL work on a clean machine and SHALL describe the real, no-elevation toolchain.
2. `HANDOFF.md` SHALL be corrected where it contradicts this spec, including the "scene not chosen"
   claim and the old grading design.
3. Each sponsor technology SHALL have a paragraph describing the specific job it does, honestly
   reflecting that segmentation is cosmetic and grading is geometric.
4. The agent log SHALL record what was built and what it caught.
5. No credential and no copyrighted clip SHALL enter git history (verifies **I5**).
6. The scene's source and licence note SHALL be recorded in its pack.

---

## Decisions

Settled with the project owner on 2026-09-19.

1. **16 hours.** The hard constraint.
2. **The clip has arrived** at `assets/private/test-scene-1/test_clip_1.mp4`, belonging to
   `test-scene-1`. The two-tier approach in D1 still stands: unit tests use synthetic keypoint
   timelines, not this file, so they stay free of copyrighted media (**I5**).
3. **Toolchain: installed** (R1 done).
4. **Grading is keypoint-based.** The earlier design scored face and body with a multimodal model and
   used ffmpeg signal heuristics as a fallback. **Rejected.** Grading now compares a skeletal
   keypoint model and face tracking. This makes **I3** possible and the game fairer.
5. **Segmentation is demoted to cosmetic** (**I9**). SAM 2 still cuts the character out, but only for
   the replay overlay. Nothing about a score depends on it, which also removes the unverified Baseten
   endpoint from the critical path.
6. **Renamed to LARPsim**, presentation layer only (**I8**).
7. **Architecture must support parallel development** (R3), while staying a single lightweight
   process.
8. **Sprites may arrive from the team**; placeholders ship meanwhile.

### D1 — Working without the clip

Two tiers, because the clip gates different things differently.

**Tier 1 — media plumbing.** A generated fixture clip (ffmpeg, rights-clean) exercises trim,
side-by-side construction, duration and dimension handling, and the media routes. It matches the real
clip's 1280×720 and 10.4 s so dimension handling is exercised identically, but it now lives in its own
gitignored scene directory rather than the real clip's path, which is occupied.

**Tier 2 — grading, testable today by fixture data, not fixture video.** A synthetic clip contains no
human, so no keypoint model will detect a pose or a face in it. Rather than pretend otherwise:

- Keypoint **comparison** is unit-tested against hand-built synthetic keypoint timelines — identical,
  mirrored, scaled, shifted, partial, and empty — which is stronger evidence than any single video.
- Keypoint **extraction** is verified against the real clip, now present — task 3.12.
- The fixture's *absence* of a detectable person is used deliberately, as the test for the
  no-person-detected path in R6.8 and R6.9.

This keeps every unit test free of copyrighted media (**I5**). The clip's arrival unblocked exactly
one task rather than the whole plan, which was the point.

### Priorities against 16 hours

| Priority | Requirements | Rationale |
|---|---|---|
| **P0 — must demo** | R1–R9, R11, R12 | Without these there is no game. |
| **P1 — protects the demo** | R10, R15 | Voices are the wow factor; fallbacks stop a dead network killing it. |
| **P2 — if time allows** | R13, R14, R16 | Replay, leaderboard, and write-ups are additive. |

WHERE time runs short, P2 SHALL be dropped before any P0 is weakened, and anything dropped SHALL be
recorded as dropped rather than silently skipped.

---

## Out of scope

Multi-scene progression · true microservice deployment · hosted infrastructure beyond a leaderboard
page · LeLamp · Sentry · Tether · Backboard · Gemini · judge-debate agents · any feature added only
to tick a sponsor box.
