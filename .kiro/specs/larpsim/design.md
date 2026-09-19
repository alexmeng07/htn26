# LARPsim — Design

**Spec:** `larpsim` · **Requirements:** `./requirements.md`

Two things changed from the previous design, and everything else follows from them: grading became
geometric, and the repo split into a `backend/` and a `frontend/` half so several people can work in
it at once. The split is folders and ownership only — an earlier draft of this document proposed an
`api/services/domain/adapters` stack inside the backend, and that was **rejected** (§3.1).

---

## 1. What grades what

| Judge | Score source | Deterministic? |
|---|---|---|
| **Body** | Pose-keypoint comparison, computed locally | Yes |
| **Face** | Facial expression-coefficient comparison, computed locally | Yes |
| **Voice** | Multimodal model over the side-by-side video | No |
| Outcome | Threshold rules in plain code | Yes |
| Wording | LLM, handed the already-decided vote | No |
| Replay overlay | SAM 2 masks | Cosmetic only |

Two of three categories are now measured rather than judged, and the vote was already code. The
model's remaining authority is the voice score and the colour commentary.

**Why this is better than the original design.** A language model asked to score posture from video
gives a different answer to the same performance on consecutive runs. That is unfair in a game, and
unfair is not funny. Geometry gives the same answer every time (**I3**), and it makes the honest
sponsor story stronger: deterministic measurement where fairness matters, a multimodal model where
nuance matters.

**What this costs.** The multimodal model does less than it used to. That is the right trade for
fairness, and its remaining job is still genuinely multimodal: it watches both performers and listens
to the player in a single pass, which no single-modality model can do. The reference sheet it writes
during prep is also what gives the judges their specificity.

---

## 2. Grading design

### 2.1 Choice of model family

Body pose and face tracking both come from **MediaPipe Tasks**, chosen because it is the only option
with a first-class implementation on *both* sides of the comparison — Python for the reference clip,
JavaScript in the browser for the live player — which is what R6.4 requires. Running two different
model families on the two sides would make the numbers incomparable, and that error would be
invisible rather than loud.

- **Pose Landmarker** — 33 body landmarks with per-landmark visibility.
- **Face Landmarker** — 478 landmarks **plus 52 blendshape coefficients**.

Model files are pinned by version, downloaded once into a gitignored assets directory, and cached.

### 2.2 Pose comparison: the reference defines the scope

Raw landmark coordinates are useless for comparison. They encode where the person stood and how tall
they are, not what they did. And a fixed list of joints is just as wrong in the other direction: it
assumes every scene shows a whole body.

**The rule (R6.7): whatever the reference shows is what gets graded.**

1. For each reference frame, determine which body parts are actually visible — a landmark counts as
   present when its `visibility` clears a threshold. That set is the **comparison scope** for that
   frame.
2. Compare only those parts, against the *same named points* on the player. Parts the reference
   doesn't show are excluded, not scored as mismatches. Parts the player shows but the reference
   doesn't are ignored, not penalised — a player sitting further back with their whole torso in shot
   is not punished for the film's framing, and gains nothing from it either.
3. Derive the measures from that scope. For a full-body shot that means the usual joint angles —
   elbows, shoulders, hips, knees, neck, torso lean. For a head-and-shoulders close-up the scope is
   small but not one-dimensional; it still yields **shoulder-line roll, neck flexion, head yaw from
   ear and nose offsets, head roll, shoulder-to-head distance** (the shrug, or the sinking down),
   **torso lean where any torso is visible, and forward/back head position**. Six or seven signals,
   not one.
4. Every measure is an angle or a ratio between points *within* the scope, so all of them are
   inherently invariant to translation and scale. That is how R6.2 is satisfied without a
   normalisation step that could itself introduce error.
5. Similarity per frame is a confidence-weighted mean absolute difference over the scope's measures,
   mapped linearly to 0–100 by `100 * (1 - error / MAX_ERROR)` and clamped, with `MAX_ERROR = 60°` as
   the single tuned constant (tasks 2.3–2.5).

**Why the scope is driven by the reference and not by the intersection of both sides:** if the player
could shrink the scope by leaving the frame, stepping back out of shot would be a way to raise the
score. Anchoring on the reference means the set of things being graded is a property of the scene, the
same for every player, every attempt.

**What this does and does not fix.** It makes a close-up *fair* — nobody is penalised for a joint the
film never showed. It does not make a close-up *rich*: the scope can never contain more than the
reference has. A 10.4 s head-and-shoulders shot is graded on head, neck and shoulders, and that is the
honest ceiling. R6.15 therefore has the report carry the number of measures actually used, so a
thin-evidence round is visible rather than silent, and the judge's line can lean on what it could
genuinely see.

**Framing is not part of this** (R6.14). A distance or framing penalty baked into the pose comparison
would directly contradict the scale invariance in R6.2 — a correct pose two feet further back would
start scoring badly, which is the exact failure invariance was written to prevent. If framing is
scored at all it is a separate, small, clearly-labelled adjustment that cannot flip a vote on its own;
the honest place for it is a nudge on the `Ready` screen, before the take, rather than a deduction
after it.

### 2.3 Face comparison: blendshapes, not landmarks

Comparing facial landmark positions between two different people measures *face shape*, not
expression — it would score a player poorly for having a different jaw. **Blendshape coefficients**
are the fix: 52 normalised values naming expressions directly (brow raise, jaw open, mouth press, eye
squint). They are person-invariant by design, which is exactly R6.3.

Similarity per frame is the mean absolute difference across coefficients, mapped to 0–100, with
expressive channels weighted above incidental ones: `brow*`, `eyeSquint*`, `jaw*` and `mouth*` at full
weight, `eyeBlink*` and `eyeLook*` at 0.1, because a blink or a glance is timing noise rather than
acting (task 2.7).

### 2.4 Time alignment

Recording and playback start on the same tick (R5.1), so timestamps already correspond. Rather than
demand exact frame alignment, each reference sample is matched against the **best-scoring player
sample within ±250 ms** of its timestamp (task 2.8, R6.5). This forgives human reaction lag without
allowing a player to match a pose from a completely different part of the scene. Because the two
clocks start together, jitter is the only error to absorb — no global time-warping or drift correction
is needed, and none should be added.

### 2.5 Aggregation

- Frames where the reference has no detection are excluded (R6.8).
- Windows around the scene's key moments are scored separately and weighted above ordinary frames
  (R6.6), because those moments are what the reference sheet describes and what the judges will quote.
- The best and worst moment come from the per-moment scores, giving the judges concrete timestamps to
  roast (R6.11).
- `player_not_visible` is set below 60% detected samples (R6.9); `player_silent` below 20% voiced
  audio (R6.10). Both defaults, tuned in task 6.7.
- Aggregation writes the **existing** `ComparisonReport` from `server/schemas.py`, not a new type, so
  the geometric path and the voice path stay interchangeable (**I7**).

### 2.6 Where extraction runs

| Side | Where | Why |
|---|---|---|
| Reference clip | Python, during prep, once | Cached in the pack; cost never touches the live round |
| Player, normal path | Browser, live during the take | Free, parallel with the performance, adds nothing to the post-take budget, and drives the live overlay |
| Player, fallback path | Python, server-side, reduced frame rate | For browsers without the capability (R5.8) |

Browser-side extraction is the reason grading adds roughly nothing to the 6–8 second wait: by the time
the take is uploaded, the player's keypoints already exist. It also means face and body scoring needs
no network at all (R6.13), which is what makes R15.2 almost free.

The fallback path shares the *same* comparison code and the same model family, so the only difference
is sampling density.

### 2.7 Testability

Comparison is a pure function over two keypoint timelines. It is unit-tested against synthetic
timelines: identical inputs score ~100, mirrored and rescaled poses still score high, unrelated poses
score low, partial visibility degrades gracefully, and empty input is handled rather than crashing.
This is stronger evidence than eyeballing one video, and it needs no clip (D1, Tier 2).

---

## 3. Architecture

### 3.1 Two halves, not layers

Requirement R3 asks for parallel development through API calls, lightweight. The honest answer is
that **what enables parallel work is stable contracts and one obvious owner per folder, not
separate processes and not extra layers.** Splitting into real microservices inside 16 hours would
add deployment, networking, and debugging cost while *reducing* the chance of a working demo. So
would introducing an `api/services/domain/adapters` stack on top of a codebase that already has one
module per concern: it would move every file, break every import, and buy nothing a hackathon demo
can spend.

So: **two halves, folders that already map to lanes, and every subsystem independently callable over
HTTP.**

```
frontend/                 React — the view the player sees

backend/
  server/
    main.py               routes + SSE event stream
    schemas.py            the shared contract — every JSON shape, one definition
    scene.py · config.py  scene pack loading, settings
    compare/              OMNI client, prompt, validation, fallback
    grading/              NEW: pose · face · align · score (pure, no I/O)
    rules/                thresholds, votes, golden buzzer (pure, no I/O)
    judges/               OpenAI personas + structured output
    voice/                ElevenLabs speech, SFX cache, voice changer
    store/                MongoDB + local JSON fallback
    media/                ffmpeg helpers
    round/                pipeline glue: ties the above together
  prep/                   Scene Prep pipeline
  tests/
```

`grading/` is the only new package. Everything else already exists at that path and stays there.

### 3.2 The rules that keep lanes from colliding

- **`schemas.py` is the contract.** Lanes agree on Pydantic models first, then build behind them.
  This is what lets the judges lane start before grading returns real numbers.
- **`grading/` and `rules/` stay pure** — no HTTP, no file, no network — so they are unit-testable
  with no fixtures and no credentials (R3.4).
- **Every module that talks to the outside world owns its own fallback.** `compare/fallback.py` is
  the pattern: same return type, no network. `FORCE_FALLBACK=1` selects them globally (R15.1), which
  is how a lane runs with no keys (R3.3).
- **`round/pipeline.py` is the only place that sequences subsystems.** Everything else is callable on
  its own, so two people editing different subsystems never touch the same file.

### 3.3 Independent HTTP surfaces

Each subsystem gets endpoints that work standalone, which is the lightweight substitute for a gateway
(R3.2). A developer on the judges lane can drive their whole feature without grading, voice, or a
camera existing:

| Surface | Purpose |
|---|---|
| `POST /grade/compare` | keypoint timelines in, category scores out |
| `POST /judges/write` | a verdict in, judge lines out |
| `POST /voice/speak` | a line and voice in, audio out |
| `GET /scene` | the active pack |
| `POST /rounds/...` | the full pipeline, composed of the above |

`round/pipeline.py` calls the same subsystem functions these routes call, not the routes themselves —
so there is one implementation, exposed two ways, and no risk of the composed path drifting from the
standalone path.

### 3.4 Not breaking what works

R3.5 is the constraint that makes this safe, and the `backend/` move already honoured it: `server/`
and `prep/` became `backend/server/` and `backend/prep/` with **no import path changes**. Tests still
import `server.main:app`, `server.rules.votes`, `server.scene`, and `server.schemas`, and pass
unchanged. Pytest resolves them via `pythonpath = ["backend"]`; the server runs as
`uvicorn --app-dir backend server.main:app`.

Because the layering is out of scope, the remaining architecture work is purely **additive**: add
`server/grading/`, fill in the stubbed modules, add the standalone routes from 3.3. No existing file
moves, so no import can break.

The existing test suite is the proof: it must stay green throughout, unchanged. Any test edit needed
to accommodate a structural change is a signal that change went too far.

---

## 4. Scene Prep

```
source clip ──trim──▶ trimmed ──┬── keypoints ──▶ reference pose + face timeline
                                ├── key moments ─▶ 6–10 timestamps
                                ├── reference sheet (one multimodal call, cached)
                                ├── segment (SAM 2, OPTIONAL, cosmetic) ──▶ isolated + masks
                                └── build pack ──▶ pack.json + MongoDB
```

Each stage skips itself when its artifact exists (R4.2), so a failure late in prep never re-runs
segmentation or a paid model call.

**Stage ordering changed.** Segmentation used to be second and blocking; it is now late and optional
(R4.14, **I9**), because only the replay needs it. A dead Baseten endpoint no longer stops a graded
round — the largest single risk reduction in this redesign.

**Key moments** are selected from the keypoint timeline rather than from pixels: the largest changes
in joint angles and blendshape coefficients are exactly the moments where the performance changes.
This is better than ffmpeg scene detection, which fires on cuts and lighting, and it needs no extra
dependency now that keypoints exist.

**Clip resolution** (R4.4, R4.5): prep looks for the configured filename; failing that, for a single
video file in the scene's private directory, which it then uses while saying loudly that it did so.
This is what makes `test_clip_1.mp4` land cleanly whatever exact name or place it arrives in, without
silently grading the wrong file.

---

## 5. The live round

```
upload take + player keypoint timeline
publish(judging)
  ├─ grade face + body        local, deterministic, ~instant      │ no network needed
  ├─ build side-by-side       ffmpeg, ~1s
  ├─ score voice              multimodal, budgeted                │ fails → local estimate
  ├─ tally                    plain code                          │ cannot fail
  ├─ write judge lines        structured LLM call                 │ fails → pre-written lines
  ├─ synthesise speech        first judge awaited, rest concurrent │ fails → bubbles + cached SFX
  ├─ persist, publish(verdict_ready)
  └─ in parallel: replay ──▶ publish(replay_ready)
```

Grading runs **first and locally**, which means that even with every external service down there is
already a real face score, a real body score, and therefore a real verdict. Degradation costs
nuance, not the round.

Per-stage elapsed time is recorded so the claimed 6–8 second wait (R11.4) is measured rather than
asserted. The replay is a separate task that cannot delay the verdict (R13.2), and its completion
event fires whether or not it succeeded, so the event stream always terminates (R11.7).

---

## 6. Degradation matrix

| Failure | Response | Round survives? |
|---|---|---|
| Multimodal model slow or down | voice falls back to a local signal estimate; face and body unaffected | Yes |
| Line writer down | pre-written lines by judge, vote, and band | Yes |
| Speech synthesis down | speech bubbles plus cached sound effects | Yes |
| MongoDB down | local JSON mirror | Yes |
| Baseten / SAM 2 down | no overlay; replay falls back to side-by-side | Yes — grading never used it |
| Browser keypoints unavailable | server-side extraction from the take | Yes |
| Whole network down | all of the above at once, via forced-fallback mode | Yes |
| No headphones | scene audio muted, subtitles shown | Yes |

Each fallback is a **named function beside the real one, returning the same type** — the pattern
`compare/fallback.py` already uses — selected by `FORCE_FALLBACK` or by the real call failing. Not
`try/except` scattered through the pipeline, and not an interface-plus-fake pair per service. That is
why forced-fallback mode is a single switch and why the offline rehearsal (R15.6) exercises the same
code path the demo will use.

---

## 7. Verification plan

**Pure unit tests, no media, no network:** pose angle extraction and comparison across identical,
mirrored, scaled, shifted, partial, and empty timelines; blendshape comparison; time-window
alignment; key-moment selection; vote tallying; fallback-line selection; leaderboard aggregation.

**Integration with fallbacks:** the whole round pipeline under `FORCE_FALLBACK=1`, asserting event
order, a complete result, and determinism across repeated runs.

**Media integration, fixture clip:** trim, side-by-side dimensions, duration, and audio-stream
presence.

**Smoke tests, real credentials, run once and logged:** multimodal describe-and-listen; structured
judge output; speech and voice design; MongoDB round trip; SAM 2 segmentation.

**Against the real clip** (`assets/private/test-scene-1/test_clip_1.mp4`, present): keypoint
extraction finds the character across the 10.4 s, the key moments land on visible expression changes,
and a human agrees the reference sheet describes the performance. This is task 3.12.

**Invariant checks:** scene swap with no code edit (**I1**); same take twice, same face and body
scores (**I3**); full round with the network off (**I6**); deliberately break segmentation and confirm
the verdict is unchanged (**I9**).

---

## 8. Sequencing against 16 hours

| Phase | Work | Exit condition |
|---|---|---|
| **0 · done** | Toolchain, dependencies, baseline | pytest, ruff, tsc, vitest green; `/health` 200 |
| **1 · ~1.5 h** | Rename; `backend/`+`frontend/` split with tests staying green | Existing suite passes unchanged; no import path moved |
| **2 · ~3 h** | Grading domain: angles, blendshapes, alignment, scoring, all unit-tested | Synthetic timelines score as expected, deterministically |
| **3 · ~2 h** | Keypoint extraction both sides; prep keypoint and key-moment stages | A pack carries a reference timeline |
| **4 · ~3 h** | Round pipeline, voice scoring, judge writing, speech | One full round to a voiced verdict |
| **5 · ~2 h** | Seven screens, placeholder sprites, SFX | The reveal reads as a show |
| **6 · ~1.5 h** | Fallbacks, offline rehearsal, threshold tuning | A round completes with the network off |
| **7 · ~1.5 h** | Replay overlay, leaderboard, docs | P2 closed out as far as time allows |
| **Reserve · ~1.5 h** | Freeze, rehearse, record a backup video | Demo rehearsed end to end |

Grading comes before the pipeline because it is the largest unknown and the thing the game's fairness
rests on. Smoke tests for paid services run early inside phase 4's front edge, so a surprise in a
third-party video payload format is found cheaply.

---

## 9. Open technical risks

1. ~~**MediaPipe on this machine.**~~ **Retired 2026-09-19.** `mediapipe 1.0.1` and `numpy 2.4.6`
   install cleanly on Python 3.11 / Windows, pulling `opencv-contrib-python` and no JAX. Both
   landmarkers construct and run on CPU through the XNNPACK delegate, and return empty results on a
   frame with no person rather than raising. Models are pinned at v1 in gitignored `assets/models/`.
   The browser-side reference-extraction contingency is not needed.
2. **Parity between Python and JavaScript landmarkers.** Same model files and the same angle and
   coefficient maths are required. Guarded by a parity test: extract the fixture both ways and
   compare.
3. **A 10.4 s close-up gives the body judge a small comparison scope.** Largely addressed by the
   reference-defined scope in §2.2: the score is computed from the six or seven measures a
   head-and-shoulders shot actually supports, nothing is penalised for being out of frame, and R6.15
   surfaces the measure count so a thin round is visible. What remains is a ceiling, not a bug — the
   scope cannot exceed what the reference shows. Watch for the body score clustering near its
   threshold during tuning (task 6.7); if it does, the body judge is rubber-stamping and a wider shot
   is the fix.
4. **Third-party multimodal payload format** is unconfirmed — content-part shape, size cap, duration
   cap. Confined to `compare/omni.py` and smoke-tested (task 4.1) before anything depends on it.
5. **Structured-output support** on the configured judge model; falls back to JSON mode plus
   validation.
6. ~~**Restructure scope creep.**~~ **Largely retired 2026-09-19.** The `backend/`+`frontend/` split
   landed with zero import changes and the suite green unchanged, and the layering that was the real
   scope risk is now explicitly out of scope (R3.1, task 1.3). What remains is the rename (task 1.1),
   guarded by the same rail: suite passes unchanged, no route path or response shape moves.
